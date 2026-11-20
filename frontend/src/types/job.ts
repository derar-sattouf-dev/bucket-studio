export type JobStatus = "pending" | "running" | "stopped" | "completed" | "failed";

export const TERMINAL_JOB_STATUSES: readonly JobStatus[] = ["completed", "stopped", "failed"];

export interface JobError {
    key: string;
    error: string;
}

export interface Job {
    job_id: string;
    status: JobStatus;
    total: number;
    skipped: number;
    processed: number;
    failed: number;
    progress_pct: number;
    elapsed_seconds: number | null;
    errors: JobError[];
    current_key: string | null;
    source_prefix: string;
    output_prefix: string;
    overwrite: boolean;
    preset_id: number | null;
    preset_name: string | null;
}

export interface StartJobRequest {
    presetId: number | null;
    overwrite: boolean;
}

/** Persisted record of a finished batch job (`GET /activity/batch-history`). */
export interface BatchHistoryItem {
    id: number;
    job_id: string;
    source_prefix: string;
    status: string;
    total: number;
    processed: number;
    failed: number;
    skipped: number;
    started_at: string | null;
    elapsed_seconds: number | null;
    completed_at: string;
}
