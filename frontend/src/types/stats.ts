export interface PipelineStats {
    total: number;
    pending: number;
    processing: number;
    /** Includes published images (publishing does not change the status). */
    processed: number;
    failed: number;
    published: number;
    job_running: boolean;
    /** Images last processed by an AI engine. */
    ai_processed: number;
    avg_seconds_per_image: number | null;
}
