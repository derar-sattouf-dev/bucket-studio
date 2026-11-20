import { Progress, Typography } from "antd";
import type { BulkPublishStatus } from "../types/image";

const { Text } = Typography;

/** Progress of the running bulk publish; renders nothing when none is running. */
export function BulkPublishProgress({ status }: { status: BulkPublishStatus | null }) {
    if (!status?.running) return null;
    const percent = status.total > 0 ? Math.floor((status.done / status.total) * 100) : 0;
    return (
        <div role="status" style={{
            marginBottom: 12, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10, padding: "10px 16px",
        }}>
            <Text strong style={{ fontSize: 13 }}>
                Publishing {status.done.toLocaleString()} of {status.total.toLocaleString()}
            </Text>
            {status.failed > 0 && <Text type="danger" style={{ fontSize: 13 }}> · {status.failed.toLocaleString()} failed</Text>}
            <Progress percent={percent} size="small" status="active" style={{ margin: 0 }} />
        </div>
    );
}
