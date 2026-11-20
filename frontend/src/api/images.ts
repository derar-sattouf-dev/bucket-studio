import type {
    BulkPublishStatus, GroupImagesPage, GroupProcessResult, GroupSelector, ImageListQuery, ImagePage, ImageStreamEvent,
    KeyResultsResponse, PagedImages, PagedImagesQuery, ProcessOptions, ProcessRequest, ResetResult, RetryResult, SyncResult,
} from "../types/image";
import { apiFetch, apiJson, streamEvents, toQuery } from "./client";

/** Groups per page of `GET /images/`. */
export const IMAGE_PAGE_SIZE = 20;
/** Images fetched per "load more" inside a group. */
export const GROUP_PAGE_SIZE = 50;
/** The API accepts at most this many keys per request; longer lists are sent in several requests. */
const MAX_KEYS_PER_REQUEST = 500;

async function inChunks<T>(keys: string[], send: (chunk: string[]) => Promise<T>): Promise<T[]> {
    const responses: T[] = [];
    for (let start = 0; start < keys.length; start += MAX_KEYS_PER_REQUEST) {
        responses.push(await send(keys.slice(start, start + MAX_KEYS_PER_REQUEST)));
    }
    return responses;
}

const groupBody = ({ group, status, search }: GroupSelector) => ({ group, status: status || null, search: search || null });

export function fetchImages({ page, status, search, sortBy, sortOrder }: ImageListQuery): Promise<ImagePage> {
    const query = toQuery({ page, page_size: IMAGE_PAGE_SIZE, sort_by: sortBy, sort_order: sortOrder, status, search });
    return apiJson<ImagePage>(`/images/${query}`);
}

/** The next images of one group, in the order of the list (`group` null = the ungrouped images). */
export function fetchGroupImages(
    group: string | null, offset: number, { status, search, sortBy, sortOrder }: Omit<ImageListQuery, "page">,
): Promise<GroupImagesPage> {
    const query = toQuery({ group, offset, limit: GROUP_PAGE_SIZE, sort_by: sortBy, sort_order: sortOrder, status, search });
    return apiJson<GroupImagesPage>(`/images/group${query}`);
}

/** One page of the processed images that are not published yet. */
export function fetchReviewQueue({ page, pageSize, search }: PagedImagesQuery): Promise<PagedImages> {
    return apiJson<PagedImages>(`/images/review${toQuery({ page, page_size: pageSize, search })}`);
}

/** One page of the failed images; `search` matches the key or the error. */
export function fetchFailedImages({ page, pageSize, search }: PagedImagesQuery): Promise<PagedImages> {
    return apiJson<PagedImages>(`/images/failed${toQuery({ page, page_size: pageSize, search })}`);
}

// ── Sync ──────────────────────────────────────────────────────────────────────

export function syncBucket(): Promise<SyncResult> {
    return apiJson<SyncResult>("/images/sync", { method: "POST" });
}

export function fetchSyncStatus(): Promise<{ syncing: boolean }> {
    return apiJson<{ syncing: boolean }>("/images/sync-status");
}

export async function cancelSync(): Promise<void> {
    await apiFetch("/images/sync/cancel", { method: "POST" });
}

// ── Processing ────────────────────────────────────────────────────────────────

export async function processImages({ keys, presetId, engine, prompt }: ProcessRequest): Promise<void> {
    await inChunks(keys, chunk => apiFetch("/images/process", {
        method: "POST",
        json: { keys: chunk, preset_id: presetId, engine, prompt: prompt || null, replace: false },
    }));
}

/** Processes every image of a group; the server collects the keys, so the group can be of any size. */
export function processGroup(group: GroupSelector, { presetId, engine, prompt }: ProcessOptions): Promise<GroupProcessResult> {
    return apiJson<GroupProcessResult>("/images/process-group", {
        method: "POST",
        json: { ...groupBody(group), preset_id: presetId, engine, prompt: prompt || null, replace: false },
    });
}

export async function abortImage(key: string): Promise<void> {
    await apiFetch("/images/abort", { method: "POST", json: { key } });
}

export function retryFailed(): Promise<RetryResult> {
    return apiJson<RetryResult>(`/images/retry-failed${toQuery({ replace: false })}`, { method: "POST" });
}

/** Streams per-key worker status until every key has finished. */
export function streamImageStatuses(
    keys: string[],
    onMessage: (event: ImageStreamEvent) => void,
    signal: AbortSignal,
): Promise<void> {
    return streamEvents<ImageStreamEvent>(`/images/stream${toQuery({ keys })}`, { onMessage, signal });
}

// ── Publish / restore ─────────────────────────────────────────────────────────

async function keyResults(path: string, keys: string[]): Promise<KeyResultsResponse> {
    const responses = await inChunks(keys, chunk => apiJson<KeyResultsResponse>(path, { method: "POST", json: { keys: chunk } }));
    return { results: responses.flatMap(response => response.results) };
}

/** Backs up each original, then writes the processed image (and derivatives) over it. */
export function publishImages(keys: string[]): Promise<KeyResultsResponse> {
    return keyResults("/images/publish", keys);
}

/** Starts publishing everything that waits for review, in the background; resolves with the image count. */
export function publishAll(): Promise<{ total: number }> {
    return apiJson<{ total: number }>("/images/publish-all", { method: "POST" });
}

/** {@link publishAll} for the publishable images of one group. */
export function publishGroup(group: GroupSelector): Promise<{ total: number }> {
    return apiJson<{ total: number }>("/images/publish-group", { method: "POST", json: groupBody(group) });
}

export function fetchBulkPublishStatus(): Promise<BulkPublishStatus> {
    return apiJson<BulkPublishStatus>("/images/publish-all/status");
}

/** Puts the backed-up original back in place. */
export function restoreImages(keys: string[]): Promise<KeyResultsResponse> {
    return keyResults("/images/restore", keys);
}

export async function resetToPending(keys: string[]): Promise<ResetResult> {
    const responses = await inChunks(keys, chunk => apiJson<ResetResult>("/images/reset-pending", { method: "POST", json: { keys: chunk } }));
    return { reset: responses.reduce((sum, response) => sum + response.reset, 0) };
}

// ── Notes ─────────────────────────────────────────────────────────────────────

export async function saveNotes(sourceKey: string, notes: string | null, tags: string | null): Promise<void> {
    await apiFetch("/images/notes", { method: "PATCH", json: { source_key: sourceKey, notes, tags } });
}
