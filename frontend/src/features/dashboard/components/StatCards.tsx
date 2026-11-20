import type { ReactNode } from "react";
import { Card } from "antd";
import {
    CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined, FieldTimeOutlined, GlobalOutlined,
    LoadingOutlined, PictureOutlined, RobotOutlined,
} from "@ant-design/icons";
import type { PipelineStats } from "../../../types/stats";

interface StatCard {
    label: string;
    value: string | number;
    color: string;
    icon: ReactNode;
    bg: string;
}

function buildCards(stats: PipelineStats): StatCard[] {
    const avg = stats.avg_seconds_per_image;
    return [
        { label: "Total images", value: stats.total, color: "#006A64", icon: <PictureOutlined />, bg: "#F4FBF9" },
        { label: "Pending", value: stats.pending, color: "#d46b08", icon: <ClockCircleOutlined />, bg: "#FFF7E6" },
        { label: "Processing", value: stats.processing, color: "#2f54eb", icon: <LoadingOutlined spin={stats.processing > 0} />, bg: "#F0F5FF" },
        { label: "Processed", value: stats.processed, color: "#2E837D", icon: <CheckCircleOutlined />, bg: "#F0FAF8" },
        { label: "Published", value: stats.published, color: "#0e7490", icon: <GlobalOutlined />, bg: "#ECFEFF" },
        { label: "Failed", value: stats.failed, color: "#BA1A1A", icon: <ExclamationCircleOutlined />, bg: "#FFF1F0" },
        { label: "Via AI", value: stats.ai_processed, color: "#722ed1", icon: <RobotOutlined />, bg: "#F9F0FF" },
        { label: "Avg time", value: avg != null ? `${avg.toFixed(1)}s` : "—", color: "#08979c", icon: <FieldTimeOutlined />, bg: "#E6FFFB" },
    ];
}

export function StatCards({ stats }: { stats: PipelineStats }) {
    return (
        <ul aria-label="Pipeline statistics" style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 20, listStyle: "none",
        }}>
            {buildCards(stats).map(({ label, value, color, icon, bg }) => (
                <li key={label}>
                    <Card size="small" style={{ borderRadius: 12, border: "1px solid #e2e8f0", background: bg }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div aria-hidden style={{
                                width: 36, height: 36, borderRadius: 10, background: `${color}18`, color, fontSize: 16,
                                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                            }}>
                                {icon}
                            </div>
                            <div>
                                <div style={{ fontSize: 10, color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                                    {label}
                                </div>
                                <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1.2, fontVariantNumeric: "tabular-nums" }}>{value}</div>
                            </div>
                        </div>
                    </Card>
                </li>
            ))}
        </ul>
    );
}
