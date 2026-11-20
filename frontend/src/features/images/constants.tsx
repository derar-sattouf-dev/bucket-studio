import type { CSSProperties, ReactNode } from "react";
import {
    CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined, GlobalOutlined, LoadingOutlined,
} from "@ant-design/icons";
import type { DisplayStatus } from "../../types/image";

/** Page heading per `?status=` filter. */
export const STATUS_HEADINGS: Record<string, { label: string; description: string }> = {
    "": { label: "Images", description: "Every image found under the source prefix, grouped by folder" },
    pending: { label: "Images · Pending", description: "Discovered but not processed yet" },
    processing: { label: "Images · Processing", description: "Being processed right now" },
    processed: { label: "Images · Processed", description: "Processed results, published or waiting for review" },
    published: { label: "Images · Published", description: "Processed images that replaced their originals (backups kept)" },
    failed: { label: "Images · Failed", description: "Errored during processing: retry or investigate" },
};

export const STATUS_TAG: Record<DisplayStatus, { color: string; icon: ReactNode; label: string }> = {
    pending: { color: "default", icon: <ClockCircleOutlined />, label: "Pending" },
    processing: { color: "processing", icon: <LoadingOutlined spin />, label: "Processing" },
    processed: { color: "success", icon: <CheckCircleOutlined />, label: "Processed" },
    failed: { color: "error", icon: <CloseCircleOutlined />, label: "Failed" },
    published: { color: "cyan", icon: <GlobalOutlined />, label: "Published" },
};

export const SORT_OPTIONS = [
    { value: "updated_at", label: "Last modified" },
    { value: "processed_at", label: "Processed at" },
    { value: "discovered_at", label: "Discovered at" },
    { value: "id", label: "Latest added" },
    { value: "source_size", label: "Source size" },
    { value: "processed_size", label: "Processed size" },
];

export const PUBLISH_BUTTON_STYLE: CSSProperties = { background: "#16a34a", borderColor: "#16a34a" };
