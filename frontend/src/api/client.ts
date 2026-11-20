/**
 * HTTP layer shared by every API module: base URL, auth header, error normalisation
 * and a fetch-based Server-Sent Events reader.
 */
import { clearToken, getToken } from "../auth/tokenStorage";

/**
 * The API is served same-origin under `/api` (nginx when deployed, the Vite dev proxy in
 * development). `VITE_API_URL` is an optional build-time override, e.g. for a separate API host.
 */
export const API_BASE: string = import.meta.env.VITE_API_URL || "/api";

// ─── Errors ───────────────────────────────────────────────────────────────────

export class ApiError extends Error {
    readonly status: number;
    /** Parsed `Retry-After` header (seconds), set on 429/503 responses when present. */
    readonly retryAfterSeconds: number | null;

    constructor(status: number, message: string, retryAfterSeconds: number | null = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.retryAfterSeconds = retryAfterSeconds;
    }
}

interface ValidationIssue {
    loc?: (string | number)[];
    msg?: string;
}

const LOCATION_PREFIXES = new Set(["body", "query", "path", "header"]);

function formatValidationIssue(issue: ValidationIssue): string | null {
    if (!issue.msg) return null;
    const field = (issue.loc ?? []).filter(part => !LOCATION_PREFIXES.has(String(part))).join(".");
    return field ? `${field}: ${issue.msg}` : issue.msg;
}

/**
 * Reads a readable message from a FastAPI error body: either `{detail: string}` or the
 * 422 validation shape `{detail: [{loc, msg}, …]}`.
 */
export function extractErrorDetail(body: unknown): string | null {
    if (!body || typeof body !== "object" || !("detail" in body)) return null;
    const { detail } = body as { detail: unknown };
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        const messages = detail
            .map(issue => (issue && typeof issue === "object" ? formatValidationIssue(issue as ValidationIssue) : null))
            .filter((message): message is string => Boolean(message));
        return messages.length ? messages.join("; ") : null;
    }
    return null;
}

export function isAbortError(error: unknown): boolean {
    return error instanceof DOMException && error.name === "AbortError";
}

/** One place to turn anything thrown by the API layer into user-facing text. */
export function getErrorMessage(error: unknown, fallback = "Something went wrong"): string {
    if (error instanceof Error && error.message) return error.message;
    return fallback;
}

function defaultMessageForStatus(status: number): string {
    if (status === 401) return "Your session has expired — please sign in again";
    if (status === 403) return "You don't have permission to do that";
    if (status === 404) return "Not found";
    if (status === 413) return "The upload is too large";
    if (status === 429) return "Too many requests — please try again later";
    if (status >= 500) return `Server error (${status})`;
    return `Request failed (${status})`;
}

function parseRetryAfter(header: string | null): number | null {
    if (!header) return null;
    const seconds = Number(header);
    if (Number.isFinite(seconds)) return Math.max(0, Math.ceil(seconds));
    const date = Date.parse(header);
    return Number.isNaN(date) ? null : Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

async function toApiError(response: Response): Promise<ApiError> {
    const body: unknown = await response.json().catch(() => null);
    const message = extractErrorDetail(body) ?? defaultMessageForStatus(response.status);
    return new ApiError(response.status, message, parseRetryAfter(response.headers.get("Retry-After")));
}

// ─── Requests ─────────────────────────────────────────────────────────────────

export interface ApiRequestInit extends Omit<RequestInit, "body"> {
    body?: BodyInit | null;
    /** Serialised as JSON with a matching Content-Type. */
    json?: unknown;
    /** Attach the bearer token and treat 401 as "session expired" (default `true`). */
    auth?: boolean;
}

/**
 * `fetch` against the API. Throws {@link ApiError} for non-2xx responses and network
 * failures; on 401 the stored token is cleared, which sends the user back to /login.
 * FormData bodies are passed through untouched so the browser sets the multipart boundary.
 */
export async function apiFetch(path: string, options: ApiRequestInit = {}): Promise<Response> {
    const { json, auth = true, headers, body, ...init } = options;
    const requestHeaders = new Headers(headers);
    let requestBody = body;

    if (json !== undefined) {
        requestHeaders.set("Content-Type", "application/json");
        requestBody = JSON.stringify(json);
    }
    const token = auth ? getToken() : null;
    if (token) requestHeaders.set("Authorization", `Bearer ${token}`);

    let response: Response;
    try {
        response = await fetch(`${API_BASE}${path}`, { ...init, headers: requestHeaders, body: requestBody });
    } catch (error) {
        if (isAbortError(error)) throw error;
        throw new ApiError(0, "Network error — could not reach the API");
    }

    if (response.status === 401 && auth) clearToken();
    if (!response.ok) throw await toApiError(response);
    return response;
}

/** {@link apiFetch} + JSON decoding of the response body. */
export async function apiJson<T>(path: string, options?: ApiRequestInit): Promise<T> {
    const response = await apiFetch(path, options);
    return (await response.json()) as T;
}

/** Builds a query string, repeating keys for array values (`?keys=a&keys=b`). */
export function toQuery(params: Record<string, string | number | boolean | string[] | null | undefined>): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === null || value === undefined || value === "") continue;
        if (Array.isArray(value)) value.forEach(item => search.append(key, item));
        else search.set(key, String(value));
    }
    const query = search.toString();
    return query ? `?${query}` : "";
}

// ─── Server-Sent Events ───────────────────────────────────────────────────────

export interface StreamEventsOptions<T> {
    onMessage: (data: T) => void;
    signal: AbortSignal;
}

// Split on CRLF, LF, or a lone CR that is not the last character (it may be half of a CRLF
// split across chunks).
const LINE_BREAK = /\r\n|\n|\r(?!$)/;

/**
 * Minimal SSE client built on `fetch`, because `EventSource` cannot send an
 * `Authorization` header. Each `data:` payload is parsed as JSON and passed to `onMessage`.
 * Resolves when the server closes the stream; rejects on HTTP/network errors and on abort.
 */
export async function streamEvents<T>(path: string, { onMessage, signal }: StreamEventsOptions<T>): Promise<void> {
    const response = await apiFetch(path, { signal, cache: "no-store", headers: { Accept: "text/event-stream" } });
    if (!response.body) throw new ApiError(0, "Streaming is not supported by this browser");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let dataLines: string[] = [];

    const dispatch = () => {
        if (dataLines.length === 0) return;
        const payload = dataLines.join("\n");
        dataLines = [];
        onMessage(JSON.parse(payload) as T);
    };

    const handleLine = (line: string) => {
        if (line === "") return dispatch();
        if (line.startsWith(":")) return; // comment / keep-alive
        const colon = line.indexOf(":");
        if ((colon === -1 ? line : line.slice(0, colon)) !== "data") return; // only `data` is used
        const value = colon === -1 ? "" : line.slice(colon + 1);
        dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
    };

    try {
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split(LINE_BREAK);
            buffer = lines.pop() ?? "";
            lines.forEach(handleLine);
        }
        buffer += decoder.decode();
        buffer.split(/\r\n|\n|\r/).forEach(handleLine);
        dispatch();
    } catch (error) {
        await reader.cancel().catch(() => undefined);
        throw error;
    }
}
