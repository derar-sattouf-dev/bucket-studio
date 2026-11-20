import type { CSSProperties } from "react";
import type { MenuProps } from "antd";
import {
    AppstoreOutlined, CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined,
    ExperimentOutlined, EyeOutlined, GlobalOutlined, HistoryOutlined, HomeOutlined, ImportOutlined,
    LoadingOutlined, PictureOutlined, QuestionCircleOutlined, SettingOutlined, TeamOutlined, ThunderboltOutlined,
    WarningOutlined,
} from "@ant-design/icons";
import { HELP_URL } from "../constants/app";

type MenuItem = Required<MenuProps>["items"][number];

/** Submenu key for "Images"; clicking its title navigates to /images. */
export const IMAGES_GROUP_KEY = "images-group";

const GROUP_LABEL_STYLE: CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: "#ffffff66",
    textTransform: "uppercase",
    padding: "14px 16px 4px",
    userSelect: "none",
};

function group(label: string, children: MenuItem[]): MenuItem {
    return { type: "group", label: <span style={GROUP_LABEL_STYLE}>{label}</span>, children };
}

interface NavOptions {
    isAdmin: boolean;
    onImagesTitleClick: () => void;
}

/** Sidebar menu. Keys of internal items are the paths they navigate to. */
export function buildNavItems({ isAdmin, onImagesTitleClick }: NavOptions): MenuItem[] {
    return [
        group("Overview", [
            { key: "/dashboard", icon: <HomeOutlined />, label: "Dashboard" },
        ]),
        group("Library", [
            {
                key: IMAGES_GROUP_KEY,
                icon: <PictureOutlined />,
                label: "Images",
                onTitleClick: onImagesTitleClick,
                children: [
                    { key: "/images?status=pending", icon: <ClockCircleOutlined />, label: "Pending" },
                    { key: "/images?status=processing", icon: <LoadingOutlined />, label: "Processing" },
                    { key: "/images?status=processed", icon: <CheckCircleOutlined />, label: "Processed" },
                    { key: "/images?status=published", icon: <GlobalOutlined />, label: "Published" },
                    { key: "/images?status=failed", icon: <ExclamationCircleOutlined />, label: "Failed" },
                ],
            },
            { key: "/review", icon: <EyeOutlined />, label: "Review" },
            { key: "/import", icon: <ImportOutlined />, label: "Import" },
            { key: "/jobs", icon: <ThunderboltOutlined />, label: "Batch jobs" },
        ]),
        group("Pipeline", [
            { key: "/presets", icon: <AppstoreOutlined />, label: "Presets" },
            { key: "/playground", icon: <ExperimentOutlined />, label: "Playground" },
        ]),
        group("Reports", [
            { key: "/failed", icon: <WarningOutlined />, label: "Failures" },
            { key: "/activity", icon: <HistoryOutlined />, label: "Activity" },
        ]),
        group("Admin", [
            ...(isAdmin ? [{ key: "/users", icon: <TeamOutlined />, label: "Users" }] : []),
            { key: "/settings", icon: <SettingOutlined />, label: "Settings" },
            {
                key: "help",
                icon: <QuestionCircleOutlined />,
                label: <a href={HELP_URL} target="_blank" rel="noopener noreferrer">Help</a>,
            },
        ]),
    ];
}
