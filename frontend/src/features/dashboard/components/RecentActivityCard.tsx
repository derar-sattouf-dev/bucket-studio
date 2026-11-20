import { useState } from "react";
import { Button, Card, Empty, Tag, Timeline, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { EVENT_META, UNKNOWN_EVENT_COLOR } from "../../../constants/activityEvents";
import type { ActivityItem } from "../../../types/activity";
import { formatTimeAgo } from "../../../utils/format";

const { Text } = Typography;

export function RecentActivityCard({ items }: { items: ActivityItem[] }) {
    const navigate = useNavigate();
    // Captured once per mount so relative times are stable across re-renders.
    const [now] = useState(() => Date.now());

    return (
        <Card
            title="Recent activity"
            size="small"
            style={{ borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}
            extra={<Button size="small" type="link" onClick={() => navigate("/activity")} style={{ fontSize: 12 }}>See all</Button>}
        >
            {items.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet" />
            ) : (
                <Timeline
                    style={{ marginTop: 8 }}
                    items={items.map(item => {
                        const meta = EVENT_META[item.event_type];
                        return {
                            color: meta?.color ?? UNKNOWN_EVENT_COLOR,
                            dot: meta?.icon,
                            children: (
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    <div>
                                        <Tag color={meta?.color ?? "default"} style={{ fontSize: 11, marginBottom: 2, borderRadius: 5 }}>
                                            {meta?.label ?? item.event_type}
                                        </Tag>
                                        {item.username && (
                                            <Tag color="default" style={{ fontSize: 11, marginBottom: 2, borderRadius: 5 }}>@{item.username}</Tag>
                                        )}
                                        <br />
                                        <Text style={{ fontSize: 13, color: "#1e293b" }}>{item.message}</Text>
                                    </div>
                                    <Text style={{ fontSize: 11, color: "#94a3b8", whiteSpace: "nowrap", marginLeft: 8 }}>
                                        {formatTimeAgo(item.created_at, now)}
                                    </Text>
                                </div>
                            ),
                        };
                    })}
                />
            )}
        </Card>
    );
}
