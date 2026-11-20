import { useState } from "react";
import { Button, Card, Popconfirm, Progress, Space, Tag, Tooltip, Typography } from "antd";
import {
    CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined, FastForwardOutlined,
    FieldTimeOutlined, FileImageOutlined, WarningOutlined,
} from "@ant-design/icons";
import type { Job } from "../../../types/job";
import { formatDuration } from "../../../utils/format";
import { JOB_STATUS_META, formatCount, progressStatus } from "../constants";

const { Text } = Typography;

/** Compact summary of a finished (or stopped) in-memory job. */
export function JobCard({ job, onDelete }: { job: Job; onDelete: (jobId: string) => void }) {
    const [showErrors, setShowErrors] = useState(false);
    const meta = JOB_STATUS_META[job.status];

    return (
        <Card size="small" style={{ marginBottom: 8, borderRadius: 10, border: `1px solid ${meta.border}`, background: meta.bg }}
              styles={{ body: { padding: "12px 16px" } }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Tag icon={meta.icon} color={meta.color} style={{ margin: 0, minWidth: 92, textAlign: "center" }}>{meta.label}</Tag>

                <div style={{ flex: 1, minWidth: 0 }}>
                    <Progress percent={Math.round(job.progress_pct)} status={progressStatus(job)} size="small" style={{ margin: 0 }} />
                </div>

                <Space size={12} style={{ flexShrink: 0 }}>
                    <Tooltip title="Processed">
                        <Text style={{ fontSize: 12 }}><CheckCircleOutlined style={{ color: "#52c41a" }} /> {formatCount(job.processed)}</Text>
                    </Tooltip>
                    <Tooltip title="Skipped">
                        <Text style={{ fontSize: 12 }} type="secondary"><FastForwardOutlined /> {formatCount(job.skipped)}</Text>
                    </Tooltip>
                    <Tooltip title="Failed">
                        <Text style={{ fontSize: 12 }} type={job.failed > 0 ? "danger" : "secondary"}>
                            <CloseCircleOutlined /> {formatCount(job.failed)}
                        </Text>
                    </Tooltip>
                    <Tooltip title="Total">
                        <Text style={{ fontSize: 12 }} type="secondary"><FileImageOutlined /> {formatCount(job.total)}</Text>
                    </Tooltip>
                    {job.elapsed_seconds != null && (
                        <Tooltip title="Elapsed">
                            <Text style={{ fontSize: 12 }} type="secondary"><FieldTimeOutlined /> {formatDuration(job.elapsed_seconds)}</Text>
                        </Tooltip>
                    )}
                </Space>

                {job.preset_name && <Tag style={{ margin: 0, flexShrink: 0 }}>{job.preset_name}</Tag>}
                <Text type="secondary" style={{ fontSize: 10, fontFamily: "monospace", flexShrink: 0 }} title={job.job_id}>
                    {job.job_id.slice(0, 8)}…
                </Text>

                <Space size={4}>
                    {job.errors.length > 0 && (
                        <Tooltip title={`${job.errors.length} error(s)`}>
                            <Button size="small" icon={<WarningOutlined />} danger onClick={() => setShowErrors(v => !v)}
                                    aria-expanded={showErrors} aria-label={`${job.errors.length} errors, show details`}>
                                {job.errors.length}
                            </Button>
                        </Tooltip>
                    )}
                    <Popconfirm title="Delete this job?" onConfirm={() => onDelete(job.job_id)} okText="Delete" okButtonProps={{ danger: true }}>
                        <Button size="small" icon={<DeleteOutlined />} type="text" aria-label="Delete job" />
                    </Popconfirm>
                </Space>
            </div>

            {showErrors && job.errors.length > 0 && (
                <div style={{
                    marginTop: 10, maxHeight: 160, overflowY: "auto", background: "#fff1f0",
                    borderRadius: 6, padding: "8px 10px", border: "1px solid #ffccc7",
                }}>
                    {job.errors.map((error, index) => (
                        <div key={index} style={{ fontSize: 11, fontFamily: "monospace", marginBottom: 4, lineHeight: 1.5 }}>
                            <Text type="secondary">{error.key}</Text>
                            <Text type="secondary"> → </Text>
                            <Text type="danger">{error.error}</Text>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
}
