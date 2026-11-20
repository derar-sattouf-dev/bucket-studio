import { useEffect, useState } from "react";
import { Spin, Table, Tag, Typography } from "antd";
import { fetchBatchHistory } from "../../../api/jobs";
import type { BatchHistoryItem } from "../../../types/job";
import { formatDuration } from "../../../utils/format";
import { HISTORY_STATUS_COLOR } from "../constants";

const { Text } = Typography;

/** Persisted history of finished batch jobs (survives restarts, unlike the in-memory list). */
export function BatchHistoryTable() {
    const [history, setHistory] = useState<BatchHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchBatchHistory(20)
            .then(setHistory)
            .catch(() => setHistory([]))
            .finally(() => setLoading(false));
    }, []);

    if (!loading && history.length === 0) return null;

    return (
        <div style={{ marginTop: 32 }}>
            <Text strong style={{ fontSize: 13, display: "block", marginBottom: 10 }}>Batch Job History</Text>
            {loading ? <Spin size="small" /> : (
                <Table<BatchHistoryItem>
                    dataSource={history}
                    rowKey="id"
                    size="small"
                    pagination={false}
                    style={{ borderRadius: 8, overflow: "hidden" }}
                    columns={[
                        {
                            title: "Date",
                            dataIndex: "completed_at",
                            render: (date: string) => <Text style={{ fontSize: 12 }}>{new Date(date).toLocaleString()}</Text>,
                        },
                        {
                            title: "Status",
                            dataIndex: "status",
                            width: 100,
                            render: (status: string) => <Tag color={HISTORY_STATUS_COLOR[status] ?? "default"}>{status}</Tag>,
                        },
                        {
                            title: "Processed",
                            dataIndex: "processed",
                            width: 100,
                            render: (n: number) => <Text style={{ fontSize: 12, color: "#2E837D" }}>{n}</Text>,
                        },
                        {
                            title: "Failed",
                            dataIndex: "failed",
                            width: 80,
                            render: (n: number) => <Text style={{ fontSize: 12, color: n > 0 ? "#BA1A1A" : undefined }}>{n}</Text>,
                        },
                        {
                            title: "Skipped",
                            dataIndex: "skipped",
                            width: 80,
                            render: (n: number) => <Text type="secondary" style={{ fontSize: 12 }}>{n}</Text>,
                        },
                        {
                            title: "Duration",
                            dataIndex: "elapsed_seconds",
                            width: 100,
                            render: (seconds: number | null) => (seconds ? formatDuration(seconds) : "—"),
                        },
                    ]}
                />
            )}
        </div>
    );
}
