import { Button, Empty, Space } from "antd";
import { ImportOutlined, SyncOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

interface ImagesEmptyStateProps {
    /** True when a status filter or search is active. */
    filtered: boolean;
    syncing: boolean;
    onSync: () => void;
    onClearFilters: () => void;
}

export function ImagesEmptyState({ filtered, syncing, onSync, onClearFilters }: ImagesEmptyStateProps) {
    const navigate = useNavigate();
    if (filtered) {
        return (
            <Empty description="No images match these filters." style={{ padding: "40px 0" }}>
                <Button onClick={onClearFilters}>Show all images</Button>
            </Empty>
        );
    }
    return (
        <Empty
            style={{ padding: "40px 0" }}
            description="No images yet. Sync the bucket to discover images under the source prefix, or import some from URLs."
        >
            <Space>
                <Button type="primary" icon={<SyncOutlined />} loading={syncing} onClick={onSync}>Sync bucket</Button>
                <Button icon={<ImportOutlined />} onClick={() => navigate("/import")}>Import from URLs</Button>
            </Space>
        </Empty>
    );
}
