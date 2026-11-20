/**
 * The only module that touches the session token.
 *
 * Trade-off: the JWT lives in localStorage, so any XSS on this origin could read it.
 * That is acceptable for a self-hosted internal dashboard served with a strict CSP
 * (`script-src 'self'`); a public multi-tenant deployment should move to httpOnly
 * cookies + CSRF protection instead.
 */

const TOKEN_KEY = "bucket-studio.token";
const EXPIRES_AT_KEY = "bucket-studio.token_expires_at";

type Listener = () => void;
const listeners = new Set<Listener>();

function notify(): void {
    listeners.forEach(listener => listener());
}

function isExpired(): boolean {
    const raw = localStorage.getItem(EXPIRES_AT_KEY);
    if (!raw) return false;
    const expiresAt = Number(raw);
    return Number.isFinite(expiresAt) && Date.now() >= expiresAt;
}

/** Returns the stored token, or `null` when absent or past its expiry. */
export function getToken(): string | null {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isExpired()) return null;
    return token;
}

export function setToken(token: string, expiresInSeconds?: number): void {
    localStorage.setItem(TOKEN_KEY, token);
    if (expiresInSeconds && expiresInSeconds > 0) {
        localStorage.setItem(EXPIRES_AT_KEY, String(Date.now() + expiresInSeconds * 1000));
    } else {
        localStorage.removeItem(EXPIRES_AT_KEY);
    }
    notify();
}

export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_AT_KEY);
    notify();
}

/** Subscribe to token changes (this tab and other tabs). Returns an unsubscribe function. */
export function subscribeToToken(listener: Listener): () => void {
    const onStorage = (event: StorageEvent) => {
        if (event.key === null || event.key === TOKEN_KEY) listener();
    };
    listeners.add(listener);
    window.addEventListener("storage", onStorage);
    return () => {
        listeners.delete(listener);
        window.removeEventListener("storage", onStorage);
    };
}
