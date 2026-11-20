import type { ProcessingEngine } from "./preset";

export type ImageStatus = "pending" | "processing" | "processed" | "failed";

/** Status shown for a group or used as a list filter; "published" is derived from `is_published`. */
export type DisplayStatus = ImageStatus | "published";

export interface ImageRecord {
    id: number;
    source_key: string;
    processed_key: string | null;
    status: ImageStatus;
    source_size: number | null;
    processed_size: number | null;
    discovered_at: string | null;
    processed_at: string | null;
    /** Last change of the record (ISO UTC); always set. */
    updated_at: string;
    error_message: string | null;
    retry_count: number;
    /** "local", "openai:<model>" or "gemini:<model>". */
    processed_by: string | null;
    source_url: string | null;
    processed_url: string | null;
    backup_url: string | null;
    is_processing: boolean;
    is_published: boolean;
    group_key: string | null;
    /** Preset used for the last processing run. */
    preset_id: number | null;
    /** Presigned URLs of the publish derivatives, keyed by file name (published images only). */
    derivative_urls: Record<string, string> | null;
    source_width: number | null;
    source_height: number | null;
    notes: string | null;
    tags: string | null;
}

/** One group of the image list; `group` is null when grouping is off or the key is too shallow. */
export interface ImageGroup {
    group: string | null;
    /** The images loaded so far: the list returns the first ones, the rest is loaded on demand. */
    images: ImageRecord[];
    /** Every image of the group that matches the list filters. */
    image_count: number;
    /** How many of those a publish would take. */
    publishable_count: number;
}

export interface ImagePage {
    items: ImageGroup[];
    /** False when grouping is off: `items` is then one page of images in a single null group. */
    grouped: boolean;
    total_images: number;
    total_groups: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface ImageListQuery {
    page: number;
    status: string;
    search: string;
    sortBy: string;
    sortOrder: string;
}

/** A page of `GET /images/review` or `GET /images/failed`. */
export interface PagedImages {
    items: ImageRecord[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface PagedImagesQuery {
    page: number;
    pageSize: number;
    search: string;
}

/** A slice of one group's images (`GET /images/group`). */
export interface GroupImagesPage {
    group: string | null;
    items: ImageRecord[];
    total: number;
    offset: number;
    limit: number;
}

/** The images of one group that match the list filters; `group` null = the ungrouped images. */
export interface GroupSelector {
    group: string | null;
    status: string;
    search: string;
}

export interface ProcessOptions {
    /** `null` uses the default preset. */
    presetId: number | null;
    engine: ProcessingEngine;
    /** Only sent for AI engines; empty means the default prompt. */
    prompt?: string;
}

export interface ProcessRequest extends ProcessOptions {
    keys: string[];
}

/** What a process run covers: chosen images, or a whole group (collected by the server). */
export type ProcessTarget =
    | { keys: string[] }
    | { group: GroupSelector; count: number; loadedKeys: string[] };

export interface GroupProcessResult {
    queued: number;
    skipped_busy: number;
}

/** Progress of the background bulk publish (`GET /images/publish-all/status`). */
export interface BulkPublishStatus {
    running: boolean;
    total: number;
    done: number;
    published: number;
    failed: number;
    started_at: string | null;
    finished_at: string | null;
    /** The first failures only. */
    errors: { key: string; error: string }[];
}

export interface SyncResult {
    synced: number;
    auto_processing?: boolean;
}

export interface RetryResult {
    queued: number;
    /** Failed images that already reached the retry limit. */
    skipped_max_retries: number;
    /** Below the limit but not requeued: already being processed, or no longer a source image. */
    skipped_other: number;
}

export interface KeyResult {
    key: string;
    status: string;
    error?: string;
}

export interface KeyResultsResponse {
    results: KeyResult[];
}

export interface ResetResult {
    reset: number;
}

/** Per-key worker state pushed by `GET /images/stream`. */
export type TaskStatus = "processing" | "done" | "failed" | "aborted";

export interface ImageStreamEvent {
    statuses: Record<string, TaskStatus>;
    all_done: boolean;
}
