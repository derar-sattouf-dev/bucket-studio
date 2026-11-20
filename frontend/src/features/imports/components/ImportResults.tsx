import { Alert, Button, Table, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import type { FailedImport, ImportedImage, ImportResult } from "../../../types/import";
import { formatBytes, pluralize } from "../../../utils/format";

const { Text } = Typography;

const urlCell = (url: string) => (
    <Text ellipsis={{ tooltip: url }} style={{ fontSize: 12, maxWidth: 420, display: "block" }}>{url}</Text>
);

/** Per-URL outcome of an import. */
export function ImportResults({ result }: { result: ImportResult }) {
    const navigate = useNavigate();
    const { imported, failed } = result;
    const type = failed.length === 0 ? "success" : imported.length === 0 ? "error" : "warning";

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }} aria-live="polite">
            <Alert
                type={type} showIcon
                title={`${imported.length} ${pluralize(imported.length, "image")} imported, ${failed.length} failed`}
                description={imported.length > 0 ? "Imported images are pending: process them from the Images page or with a batch job." : undefined}
                action={imported.length > 0 && <Button size="small" onClick={() => navigate("/images?status=pending")}>View pending</Button>}
            />
            {imported.length > 0 && (
                <Table<ImportedImage>
                    title={() => <Text strong>Imported</Text>}
                    dataSource={imported} rowKey="url" size="small" pagination={false}
                    columns={[
                        { title: "URL", dataIndex: "url", render: urlCell },
                        { title: "Stored as", dataIndex: "key", render: (key: string) => <Text code copyable style={{ fontSize: 12 }}>{key}</Text> },
                        { title: "Size", dataIndex: "size", width: 100, render: (size: number) => formatBytes(size) },
                    ]}
                />
            )}
            {failed.length > 0 && (
                <Table<FailedImport>
                    title={() => <Text strong type="danger">Failed</Text>}
                    dataSource={failed} rowKey="url" size="small" pagination={false}
                    columns={[
                        { title: "URL", dataIndex: "url", render: urlCell },
                        { title: "Reason", dataIndex: "error", render: (error: string) => <Text type="danger" style={{ fontSize: 12 }}>{error}</Text> },
                    ]}
                />
            )}
        </div>
    );
}
