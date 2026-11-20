import type { CSSProperties } from "react";
import { Alert, Descriptions, Drawer, Space, Tooltip, Typography } from "antd";
import { EngineTag } from "../../../components/EngineTag";
import type { ImageRecord } from "../../../types/image";
import { formatBytes } from "../../../utils/format";
import { dimensionsLabel, displayStatus, fileName } from "../imageUtils";
import { DerivativeList } from "./DerivativeList";
import { DrawerComparison } from "./DrawerComparison";
import { ImageActionButtons } from "./ImageActionButtons";
import { NotesEditor } from "./NotesEditor";
import { StatusTag } from "./StatusTags";
import type { ImageActionHandlers, ImageBusyState } from "./types";

const { Text } = Typography;

const SECTION_LABEL: CSSProperties = {
    fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", margin: "0 0 8px",
};

interface ImageDetailDrawerProps {
    image: ImageRecord | null;
    /** Name of the preset used for the last run, when known. */
    presetName: (presetId: number | null) => string | null;
    onClose: () => void;
    handlers: ImageActionHandlers;
    busy: ImageBusyState;
}

const KeyText = ({ value }: { value: string }) => (
    <Text copyable style={{ fontSize: 11, wordBreak: "break-all" }}>{value}</Text>
);

/** Full-size comparison, metadata, derivatives, notes and actions for a single image. */
export function ImageDetailDrawer({ image, presetName, onClose, handlers, busy }: ImageDetailDrawerProps) {
    if (!image) return null;
    const dimensions = dimensionsLabel(image);

    return (
        <Drawer
            open
            onClose={onClose}
            size="min(1160px, 92vw)"
            title={
                <Space>
                    <StatusTag status={displayStatus(image)} />
                    <Tooltip title={image.source_key}><span>{fileName(image.source_key)}</span></Tooltip>
                </Space>
            }
            styles={{ body: { padding: "20px 24px" } }}
        >
            <DrawerComparison image={image} />

            {image.error_message && (
                <Alert
                    type="error" showIcon style={{ marginBottom: 16 }}
                    title={image.error_message}
                    description={image.retry_count > 0 ? `Retried ${image.retry_count} times` : undefined}
                />
            )}

            {image.is_published && (
                <div style={{ marginBottom: 20 }}>
                    <h3 style={SECTION_LABEL}>Published derivatives</h3>
                    <DerivativeList urls={image.derivative_urls ?? {}} />
                </div>
            )}

            <Descriptions size="small" column={2} bordered style={{ marginBottom: 20 }}>
                <Descriptions.Item label="Source key" span={2}><KeyText value={image.source_key} /></Descriptions.Item>
                {image.processed_key && (
                    <Descriptions.Item label="Processed key" span={2}><KeyText value={image.processed_key} /></Descriptions.Item>
                )}
                <Descriptions.Item label="Group">{image.group_key ?? "None"}</Descriptions.Item>
                <Descriptions.Item label="Preset">{presetName(image.preset_id) ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="Original">
                    {[dimensions, formatBytes(image.source_size)].filter(Boolean).join(" · ")}
                </Descriptions.Item>
                <Descriptions.Item label="Result">{formatBytes(image.processed_size)}</Descriptions.Item>
                <Descriptions.Item label="Engine">
                    {image.status === "processed" && image.processed_by ? <EngineTag processedBy={image.processed_by} /> : "—"}
                </Descriptions.Item>
                <Descriptions.Item label="Retries">{image.retry_count}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginBottom: 20 }}>
                <h3 style={SECTION_LABEL}>Notes & tags</h3>
                <NotesEditor image={image} onSave={handlers.onSaveNotes} />
            </div>

            <ImageActionButtons image={image} variant="drawer" handlers={handlers} busy={busy} />
        </Drawer>
    );
}
