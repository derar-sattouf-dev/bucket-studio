import { Button, Popconfirm, Space, Tooltip } from "antd";
import { CloseCircleOutlined, CloudUploadOutlined, RollbackOutlined, ThunderboltOutlined, UndoOutlined } from "@ant-design/icons";
import type { ImageRecord } from "../../../types/image";
import { PUBLISH_BUTTON_STYLE } from "../constants";
import { isBusy, isResettable } from "../imageUtils";
import type { ImageActionHandlers, ImageBusyState } from "./types";

interface ImageActionButtonsProps {
    image: ImageRecord;
    /** "row": compact (table row); "drawer": regular size. */
    variant: "row" | "drawer";
    handlers: Pick<ImageActionHandlers, "onProcess" | "onPublish" | "onRestore" | "onReset" | "onAbort">;
    busy: ImageBusyState;
}

/** Actions available for a single image, depending on its state. */
export function ImageActionButtons({ image, variant, handlers, busy }: ImageActionButtonsProps) {
    const size = variant === "row" ? "small" : undefined;
    const keys = [image.source_key];

    if (isBusy(image)) {
        return (
            <Button size={size} danger icon={<CloseCircleOutlined />} loading={busy.aborting.has(image.source_key)}
                    onClick={() => handlers.onAbort(image.source_key)}>
                Stop
            </Button>
        );
    }

    const canPublish = image.status === "processed" && !image.is_published;
    const processLabel = image.status === "failed" ? "Retry" : image.status === "pending" ? "Process" : "Reprocess";

    return (
        <Space size={4} wrap>
            {canPublish && (
                <Tooltip title="Replace the original with this result (the original is backed up first)">
                    <Button size={size} type="primary" icon={<CloudUploadOutlined />} style={PUBLISH_BUTTON_STYLE}
                            loading={busy.publishing} onClick={() => handlers.onPublish(keys)}>
                        Publish
                    </Button>
                </Tooltip>
            )}
            <Button size={size} icon={<ThunderboltOutlined />} onClick={() => handlers.onProcess(keys)}>{processLabel}</Button>
            {image.is_published && (
                <Popconfirm
                    title="Restore the original?"
                    description="The backed-up original goes back in place and the image returns to pending."
                    okText="Restore" onConfirm={() => handlers.onRestore(keys)}
                >
                    <Button size={size} danger icon={<RollbackOutlined />} loading={busy.restoring}>Restore</Button>
                </Popconfirm>
            )}
            {isResettable(image) && (
                <Tooltip title="Back to pending; discards the processed result (the source file is untouched)">
                    <Button size={size} icon={<UndoOutlined />} loading={busy.resetting} onClick={() => handlers.onReset(keys)}>
                        Reset
                    </Button>
                </Tooltip>
            )}
        </Space>
    );
}
