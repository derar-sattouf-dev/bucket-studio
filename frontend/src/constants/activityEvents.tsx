import type { ReactNode } from "react";
import {
    AppstoreOutlined, CheckCircleOutlined, CloseCircleOutlined, CloudUploadOutlined, DeleteOutlined,
    ImportOutlined, PauseCircleOutlined, ReloadOutlined, SettingOutlined, SyncOutlined, TeamOutlined,
    ThunderboltOutlined,
} from "@ant-design/icons";

interface EventMeta {
    color: string;
    icon: ReactNode;
    label: string;
}

/** Display metadata for activity-log event types (unknown types fall back to grey). */
export const EVENT_META: Record<string, EventMeta> = {
    sync: { color: "#006A64", icon: <SyncOutlined />, label: "Sync" },
    batch_start: { color: "#1677ff", icon: <ThunderboltOutlined />, label: "Batch start" },
    batch_complete: { color: "#2f54eb", icon: <ThunderboltOutlined />, label: "Batch complete" },
    process: { color: "#08979c", icon: <ThunderboltOutlined />, label: "Image processed" },
    publish: { color: "#2E837D", icon: <CloudUploadOutlined />, label: "Image published" },
    restore: { color: "#fa8c16", icon: <ReloadOutlined />, label: "Image restored" },
    auto_process: { color: "#722ed1", icon: <ThunderboltOutlined />, label: "Auto-process" },
    "auth.login": { color: "#52c41a", icon: <CheckCircleOutlined />, label: "Sign-in" },
    "auth.login_failed": { color: "#ff4d4f", icon: <CloseCircleOutlined />, label: "Sign-in failed" },
    "image.process": { color: "#08979c", icon: <ThunderboltOutlined />, label: "Process request" },
    "image.publish": { color: "#2E837D", icon: <CloudUploadOutlined />, label: "Publish request" },
    "image.publish_all": { color: "#2E837D", icon: <CloudUploadOutlined />, label: "Publish all" },
    "image.restore": { color: "#fa8c16", icon: <ReloadOutlined />, label: "Restore request" },
    "import.created": { color: "#13c2c2", icon: <ImportOutlined />, label: "Import" },
    "job.start": { color: "#1677ff", icon: <ThunderboltOutlined />, label: "Job start" },
    "job.stop": { color: "#faad14", icon: <PauseCircleOutlined />, label: "Job stop" },
    "preset.created": { color: "#722ed1", icon: <AppstoreOutlined />, label: "Preset created" },
    "preset.updated": { color: "#722ed1", icon: <AppstoreOutlined />, label: "Preset updated" },
    "preset.deleted": { color: "#ff4d4f", icon: <AppstoreOutlined />, label: "Preset deleted" },
    "preset.default": { color: "#722ed1", icon: <AppstoreOutlined />, label: "Default preset" },
    "settings.changed": { color: "#722ed1", icon: <SettingOutlined />, label: "Settings" },
    "settings.admin_changed": { color: "#fa8c16", icon: <SettingOutlined />, label: "Admin settings" },
    "settings.reset_db": { color: "#ff4d4f", icon: <DeleteOutlined />, label: "Database reset" },
    "user.created": { color: "#52c41a", icon: <TeamOutlined />, label: "User created" },
    "user.deleted": { color: "#ff4d4f", icon: <CloseCircleOutlined />, label: "User deleted" },
};

export const UNKNOWN_EVENT_COLOR = "#BEC9C6";

export const EVENT_FILTER_OPTIONS = [
    { value: "all", label: "All events" },
    ...Object.entries(EVENT_META).map(([value, { label }]) => ({ value, label })),
];
