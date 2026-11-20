import type { ReactNode } from "react";
import {
    CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined, PauseCircleOutlined, SyncOutlined,
} from "@ant-design/icons";
import type { Job, JobStatus } from "../../types/job";

export const JOB_STATUS_META: Record<JobStatus, { color: string; icon: ReactNode; label: string; bg: string; border: string }> = {
    pending: { color: "default", icon: <ClockCircleOutlined />, label: "Pending", bg: "#fafafa", border: "#d9d9d9" },
    running: { color: "processing", icon: <SyncOutlined spin />, label: "Running", bg: "#e6f4ff", border: "#1677ff" },
    completed: { color: "success", icon: <CheckCircleOutlined />, label: "Completed", bg: "#f6ffed", border: "#52c41a" },
    stopped: { color: "warning", icon: <PauseCircleOutlined />, label: "Stopped", bg: "#fffbe6", border: "#faad14" },
    failed: { color: "error", icon: <CloseCircleOutlined />, label: "Failed", bg: "#fff2f0", border: "#ff4d4f" },
};

export const HISTORY_STATUS_COLOR: Record<string, string> = {
    completed: "success",
    stopped: "warning",
    failed: "error",
};

export function progressStatus(job: Job): "success" | "exception" | "active" {
    if (job.status === "completed") return "success";
    if (job.status === "failed" || job.failed > 0) return "exception";
    return "active";
}

export const formatCount = (n: number) => n.toLocaleString();
