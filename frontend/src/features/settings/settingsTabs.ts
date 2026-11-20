import type { ComponentType } from "react";
import {
    CloudServerOutlined, DashboardOutlined, DatabaseOutlined, ExclamationCircleOutlined,
    RobotOutlined, SafetyOutlined, SlidersOutlined, SyncOutlined,
} from "@ant-design/icons";

/** Where a tab's changes are saved: the runtime form, the password-protected draft, or nowhere. */
export type TabKind = "runtime" | "admin" | "readonly";

export interface SettingsTab {
    key: string;
    label: string;
    Icon: ComponentType;
    kind: TabKind;
}

export const SETTINGS_TABS: SettingsTab[] = [
    { key: "general", label: "General", Icon: SlidersOutlined, kind: "runtime" },
    { key: "sync", label: "Sync & processing", Icon: SyncOutlined, kind: "runtime" },
    { key: "ai", label: "AI engines", Icon: RobotOutlined, kind: "runtime" },
    { key: "limits", label: "Limits", Icon: DashboardOutlined, kind: "runtime" },
    { key: "storage", label: "Storage & publishing", Icon: DatabaseOutlined, kind: "admin" },
    { key: "security", label: "Security", Icon: SafetyOutlined, kind: "admin" },
    { key: "environment", label: "Environment", Icon: CloudServerOutlined, kind: "readonly" },
    { key: "danger", label: "Danger zone", Icon: ExclamationCircleOutlined, kind: "readonly" },
];

export const DEFAULT_TAB = SETTINGS_TABS[0];

export function findTab(key: string | null): SettingsTab {
    return SETTINGS_TABS.find(tab => tab.key === key) ?? DEFAULT_TAB;
}

