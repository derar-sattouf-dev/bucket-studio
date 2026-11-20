import type { PipelineStats } from "../types/stats";
import { apiJson } from "./client";

export function fetchPipelineStats(): Promise<PipelineStats> {
    return apiJson<PipelineStats>("/stats/");
}
