export interface ActivityItem {
    id: number;
    event_type: string;
    message: string;
    meta: string | null;
    created_at: string;
    username?: string | null;
}
