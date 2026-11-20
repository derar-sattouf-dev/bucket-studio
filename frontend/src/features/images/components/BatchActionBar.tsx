import { Button, Popconfirm, Typography } from "antd";
import { CloudUploadOutlined, RollbackOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { pluralize } from "../../../utils/format";
import { PUBLISH_BUTTON_STYLE } from "../constants";
import type { BusyFlag } from "../hooks/useImageActions";
import type { ImageActionHandlers } from "./types";

const { Text } = Typography;

interface BatchActionBarProps {
    keys: { all: string[]; publishable: string[]; published: string[] };
    busy: Record<BusyFlag, boolean>;
    handlers: Pick<ImageActionHandlers, "onProcess" | "onPublish" | "onRestore">;
    onDeselect: () => void;
}

/** Bulk actions for the selected images. */
export function BatchActionBar({ keys, busy, handlers, onDeselect }: BatchActionBarProps) {
    return (
        <div role="toolbar" aria-label="Selected images" style={{
            marginBottom: 12, background: "#f0f9ff", border: "1px solid #bae0ff", borderRadius: 10,
            padding: "10px 16px", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
        }}>
            <Text strong style={{ fontSize: 13, color: "#0369a1" }}>
                {keys.all.length} {pluralize(keys.all.length, "image")} selected
            </Text>
            <Button size="small" type="primary" icon={<ThunderboltOutlined />} loading={busy.processing}
                    onClick={() => handlers.onProcess(keys.all)}>
                Process…
            </Button>
            {keys.publishable.length > 0 && (
                <Popconfirm
                    title={`Publish ${keys.publishable.length} ${pluralize(keys.publishable.length, "image")}?`}
                    description="Each original is backed up, then replaced by its processed result."
                    okText="Publish" onConfirm={() => handlers.onPublish(keys.publishable)}
                >
                    <Button size="small" type="primary" icon={<CloudUploadOutlined />} style={PUBLISH_BUTTON_STYLE} loading={busy.publishing}>
                        Publish {keys.publishable.length}
                    </Button>
                </Popconfirm>
            )}
            {keys.published.length > 0 && (
                <Popconfirm
                    title={`Restore ${keys.published.length} ${pluralize(keys.published.length, "original")}?`}
                    okText="Restore" onConfirm={() => handlers.onRestore(keys.published)}
                >
                    <Button size="small" danger icon={<RollbackOutlined />} loading={busy.restoring}>
                        Restore {keys.published.length}
                    </Button>
                </Popconfirm>
            )}
            <Button size="small" type="link" style={{ marginLeft: "auto", padding: 0 }} onClick={onDeselect}>Deselect</Button>
        </div>
    );
}
