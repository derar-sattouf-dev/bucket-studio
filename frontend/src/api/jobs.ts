import type { BatchHistoryItem, Job, StartJobRequest } from "../types/job";
import { apiFetch, apiJson, streamEvents } from "./client";

export function fetchJobs(): Promise<Job[]> {
    return apiJson<Job[]>("/jobs/");
}

export function fetchJob(jobId: string): Promise<Job> {
    return apiJson<Job>(`/jobs/${encodeURIComponent(jobId)}`);
}

/** Processes every pending image under the source prefix with one preset (`null` = default). */
export function startJob({ presetId, overwrite }: StartJobRequest): Promise<Job> {
    return apiJson<Job>("/jobs/start", { method: "POST", json: { preset_id: presetId, overwrite_original: overwrite } });
}

export function stopJob(jobId: string): Promise<Job> {
    return apiJson<Job>(`/jobs/${encodeURIComponent(jobId)}/stop`, { method: "POST" });
}

export function skipCurrentImage(jobId: string): Promise<Job> {
    return apiJson<Job>(`/jobs/${encodeURIComponent(jobId)}/skip`, { method: "POST" });
}

export async function deleteJob(jobId: string): Promise<void> {
    await apiFetch(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}

/** Streams job snapshots (about one per second) until the job reaches a terminal state. */
export function streamJob(jobId: string, onMessage: (job: Job) => void, signal: AbortSignal): Promise<void> {
    return streamEvents<Job>(`/jobs/${encodeURIComponent(jobId)}/stream`, { onMessage, signal });
}

export function fetchBatchHistory(limit = 20): Promise<BatchHistoryItem[]> {
    return apiJson<BatchHistoryItem[]>(`/activity/batch-history?limit=${limit}`);
}
