import { Badge, Button, Card, Popconfirm, Typography } from "antd";
import { CloudUploadOutlined, ExclamationCircleOutlined, EyeOutlined, ImportOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { BulkPublishProgress } from "../../../components/BulkPublishProgress";
import type { BulkPublishStatus } from "../../../types/image";
import type { PipelineStats } from "../../../types/stats";
import { SyncButtons, type SyncState } from "./SyncButtons";

const { Text } = Typography;

interface QuickActionsCardProps {
    stats: PipelineStats;
    /** Processed but not published yet. */
    awaitingReview: number;
    sync: SyncState;
    publishing: boolean;
    /** Progress of the running bulk publish, if any. */
    publishStatus: BulkPublishStatus | null;
    onPublishAll: () => void;
}

export function QuickActionsCard({ stats, awaitingReview, sync, publishing, publishStatus, onPublishAll }: QuickActionsCardProps) {
    const navigate = useNavigate();
    return (
        <Card title="Quick actions" size="small" style={{ borderRadius: 12, height: "100%" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", gap: 8 }}><SyncButtons {...sync} block /></div>
                <Button block icon={<ImportOutlined />} onClick={() => navigate("/import")}>Import from URLs</Button>
                <Button block icon={<ThunderboltOutlined />} onClick={() => navigate("/jobs")}>Start a batch job</Button>
                <Button block icon={<EyeOutlined />} onClick={() => navigate("/review")} disabled={awaitingReview === 0}>
                    Review {awaitingReview} processed
                </Button>
                <Popconfirm
                    title={`Publish all ${awaitingReview} processed images?`}
                    description="Each original is backed up, then replaced by its processed result."
                    okText="Publish all" onConfirm={onPublishAll} disabled={awaitingReview === 0 || publishing}
                >
                    <Button block type="primary" icon={<CloudUploadOutlined />} loading={publishing} disabled={awaitingReview === 0}>
                        Publish all ({awaitingReview})
                    </Button>
                </Popconfirm>
                <BulkPublishProgress status={publishStatus} />
                {stats.failed > 0 && (
                    <Button block danger icon={<ExclamationCircleOutlined />} onClick={() => navigate("/failed")}>
                        See {stats.failed} failed
                    </Button>
                )}
                {stats.job_running && <Badge status="processing" text={<Text style={{ fontSize: 13 }}>A batch job is running</Text>} />}
            </div>
        </Card>
    );
}
