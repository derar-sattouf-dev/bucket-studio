import type { ActivityItem } from "../types/activity";
import { apiJson, toQuery } from "./client";

export function fetchActivity(limit: number, search?: string): Promise<ActivityItem[]> {
    return apiJson<ActivityItem[]>(`/activity/${toQuery({ limit, search })}`);
}
