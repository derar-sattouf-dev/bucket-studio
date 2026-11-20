import { useId } from "react";
import { Button, Input, Segmented, Typography, Upload } from "antd";
import { DeleteOutlined, InboxOutlined, LinkOutlined, UploadOutlined } from "@ant-design/icons";
import { formatBytes } from "../../../utils/format";

const { Text } = Typography;

export type SourceMode = "file" | "url";

interface SourcePickerProps {
    mode: SourceMode;
    onModeChange: (mode: SourceMode) => void;
    file: File | null;
    onFileChange: (file: File | null) => void;
    url: string;
    onUrlChange: (url: string) => void;
    disabled?: boolean;
}

/** Choose the test image: an upload (kept in memory) or a public URL fetched by the server. */
export function SourcePicker({ mode, onModeChange, file, onFileChange, url, onUrlChange, disabled }: SourcePickerProps) {
    const id = useId();
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Segmented<SourceMode>
                block
                value={mode}
                onChange={onModeChange}
                disabled={disabled}
                options={[
                    { value: "file", label: "Upload", icon: <UploadOutlined /> },
                    { value: "url", label: "From URL", icon: <LinkOutlined /> },
                ]}
            />
            {mode === "file" && (file ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #e2e8f0", borderRadius: 8, padding: "8px 12px" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <Text strong ellipsis style={{ display: "block" }}>{file.name}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>{formatBytes(file.size)}</Text>
                    </div>
                    <Button icon={<DeleteOutlined />} onClick={() => onFileChange(null)} disabled={disabled} aria-label="Remove file" />
                </div>
            ) : (
                <Upload.Dragger
                    accept="image/*"
                    multiple={false}
                    showUploadList={false}
                    disabled={disabled}
                    // Returning false keeps antd from uploading; the file is sent when you run the preset.
                    beforeUpload={selected => { onFileChange(selected); return false; }}
                >
                    <p className="ant-upload-drag-icon"><InboxOutlined style={{ color: "#006A64" }} /></p>
                    <p className="ant-upload-text">Click or drop an image</p>
                    <p className="ant-upload-hint">Processed in memory, never stored</p>
                </Upload.Dragger>
            ))}
            {mode === "url" && (
                <div>
                    <label htmlFor={`${id}-url`} className="sr-only">Image URL</label>
                    <Input id={`${id}-url`} value={url} onChange={event => onUrlChange(event.target.value)} disabled={disabled}
                           placeholder="https://example.com/photo.jpg" prefix={<LinkOutlined />} allowClear />
                    <Text type="secondary" style={{ fontSize: 12 }}>The server downloads it; private network addresses are refused.</Text>
                </div>
            )}
        </div>
    );
}
