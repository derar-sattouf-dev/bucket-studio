import { Button, Card, Col, Progress, Row, Space, Tooltip, Typography } from "antd";
import {
    CheckCircleOutlined, CloseCircleOutlined, FastForwardOutlined, FieldTimeOutlined, FileImageOutlined,
    ForwardOutlined, StopOutlined, SyncOutlined, ThunderboltOutlined,
} from "@ant-design/icons";
import type { Job } from "../../../types/job";
import { formatDuration } from "../../../utils/format";
import { formatCount } from "../constants";

const { Text, Title } = Typography;

interface RunningJobBannerProps {
    job: Job;
    onStop: (jobId: string) => void;
    onSkip: (jobId: string) => void;
}

/** Live progress, throughput and controls for the job that is currently running. */
export function RunningJobBanner({ job, onStop, onSkip }: RunningJobBannerProps) {
    const done = job.processed + job.failed;
    const remaining = job.total - done;
    const rate = job.elapsed_seconds && done ? done / job.elapsed_seconds : null;
    const eta = rate && remaining ? Math.round(remaining / rate) : null;

    const stats = [
        { title: "Processed", value: job.processed, color: "#52c41a", icon: <CheckCircleOutlined /> },
        { title: "Skipped", value: job.skipped, color: "#8c8c8c", icon: <FastForwardOutlined /> },
        { title: "Failed", value: job.failed, color: job.failed > 0 ? "#ff4d4f" : "#8c8c8c", icon: <CloseCircleOutlined /> },
        { title: "Total", value: job.total, color: "#1677ff", icon: <FileImageOutlined /> },
        { title: "Elapsed", value: formatDuration(job.elapsed_seconds), color: "#595959", icon: <FieldTimeOutlined /> },
        { title: "Rate", value: rate ? `${rate.toFixed(1)}/s` : "—", color: "#595959", icon: <ThunderboltOutlined /> },
    ];

    return (
        <Card
            style={{
                marginBottom: 24, borderRadius: 16, border: "1.5px solid #1677ff",
                background: "linear-gradient(135deg, #e6f4ff 0%, #f0f5ff 100%)",
                boxShadow: "0 4px 24px rgba(22,119,255,0.08)",
            }}
            styles={{ body: { padding: 24 } }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                <Space align="center" size={10}>
                    <div style={{
                        width: 36, height: 36, borderRadius: "50%", background: "#1677ff",
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                        <SyncOutlined spin style={{ color: "#fff", fontSize: 16 }} />
                    </div>
                    <div>
                        <Title level={5} style={{ margin: 0, color: "#1677ff" }}>
                            Batch job running{job.preset_name ? ` · ${job.preset_name}` : ""}
                        </Title>
                        <Text type="secondary" style={{ fontSize: 11, fontFamily: "monospace" }}>{job.job_id}</Text>
                    </div>
                </Space>
                <Space>
                    <Tooltip title="Skip current image and move to next">
                        <Button icon={<ForwardOutlined />} onClick={() => onSkip(job.job_id)} disabled={!job.current_key}>Skip</Button>
                    </Tooltip>
                    <Button danger icon={<StopOutlined />} type="primary" onClick={() => onStop(job.job_id)}>Stop job</Button>
                </Space>
            </div>

            <Progress
                percent={Math.round(job.progress_pct)}
                status="active"
                strokeColor={{ from: "#1677ff", to: "#52c41a" }}
                size={{ height: 10 }}
                style={{ marginBottom: 4 }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>{formatCount(done)} of {formatCount(job.total)} images</Text>
                {eta != null && <Text type="secondary" style={{ fontSize: 12 }}>ETA ~{formatDuration(eta)}</Text>}
            </div>

            {job.current_key && (
                <div style={{
                    marginBottom: 20, padding: "8px 12px", background: "#fff", borderRadius: 8,
                    border: "1px solid #d0e4ff", fontSize: 12, fontFamily: "monospace", color: "#595959",
                    display: "flex", alignItems: "center", gap: 8,
                }}>
                    <SyncOutlined spin style={{ color: "#1677ff", flexShrink: 0 }} />
                    <Text style={{ fontSize: 12, flex: 1 }} ellipsis>{job.current_key}</Text>
                </div>
            )}

            <Row gutter={16}>
                {stats.map(({ title, value, color, icon }) => (
                    <Col key={title} xs={12} sm={8} md={4}>
                        <Card size="small" style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8f0fe", textAlign: "center" }}
                              styles={{ body: { padding: "10px 8px" } }}>
                            <div style={{ color, fontSize: 18, marginBottom: 2 }}>{icon}</div>
                            <div style={{ fontWeight: 700, fontSize: 18, color, lineHeight: 1.2 }}>{value}</div>
                            <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>{title}</div>
                        </Card>
                    </Col>
                ))}
            </Row>
        </Card>
    );
}
