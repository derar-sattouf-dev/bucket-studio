import { useEffect } from "react";
import { fetchJob, streamJob } from "../../../api/jobs";
import { TERMINAL_JOB_STATUSES, type Job } from "../../../types/job";

const POLL_INTERVAL_MS = 2000;

const isFinished = (job: Job) => TERMINAL_JOB_STATUSES.includes(job.status);

/**
 * Live updates for a running job over SSE. If the stream fails or drops before the job
 * finishes, falls back to polling `GET /jobs/{id}` every 2 s.
 */
export function useJobStream(jobId: string | null, onUpdate: (job: Job) => void) {
    useEffect(() => {
        if (!jobId) return;
        const controller = new AbortController();
        let pollTimer: ReturnType<typeof setInterval> | null = null;
        let finished = false;

        const stopPolling = () => {
            if (pollTimer !== null) clearInterval(pollTimer);
            pollTimer = null;
        };
        const handle = (job: Job) => {
            onUpdate(job);
            if (isFinished(job)) finished = true;
        };
        const startPolling = () => {
            if (finished || controller.signal.aborted) return;
            pollTimer = setInterval(() => {
                fetchJob(jobId)
                    .then(job => {
                        handle(job);
                        if (finished) stopPolling();
                    })
                    .catch(stopPolling);
            }, POLL_INTERVAL_MS);
        };

        streamJob(jobId, handle, controller.signal).then(startPolling, startPolling);

        return () => {
            controller.abort();
            stopPolling();
        };
    }, [jobId, onUpdate]);
}
