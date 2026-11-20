import type { KeyResult } from "../types/image";

/** Splits per-key results of publish/restore into successes and failures. */
export function summarizeResults(results: KeyResult[]): { succeeded: number; failed: KeyResult[] } {
    const failed = results.filter(result => result.status === "error");
    return { succeeded: results.length - failed.length, failed };
}
