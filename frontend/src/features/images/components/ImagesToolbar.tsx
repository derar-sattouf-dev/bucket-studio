import { Button, Input, Select, Space, Tag, Typography } from "antd";
import { ReloadOutlined, SortAscendingOutlined, SortDescendingOutlined, SyncOutlined } from "@ant-design/icons";
import type { ImageListQuery, ImagePage } from "../../../types/image";
import { pluralize } from "../../../utils/format";
import { SORT_OPTIONS } from "../constants";

const { Text } = Typography;

interface ImagesToolbarProps {
    query: ImageListQuery;
    data: ImagePage | null;
    sync: { syncing: boolean; autoSyncing: boolean; onSync: () => void; onCancel: () => void };
    retrying: boolean;
    onRetryFailed: () => void;
    onChangeParams: (patch: Record<string, string>) => void;
}

export function ImagesToolbar({ query, data, sync, retrying, onRetryFailed, onChangeParams }: ImagesToolbarProps) {
    const descending = query.sortOrder === "desc";
    return (
        <div style={{
            background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 10,
            padding: "10px 16px", marginBottom: 12,
            display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
        }}>
            <Space size={6}>
                {sync.autoSyncing && !sync.syncing && <Tag icon={<SyncOutlined spin />} color="processing">Auto-syncing</Tag>}
                <Button icon={<SyncOutlined />} onClick={sync.onSync} loading={sync.syncing}>Sync bucket</Button>
                {(sync.syncing || sync.autoSyncing) && <Button danger onClick={sync.onCancel}>Stop</Button>}
            </Space>
            <Button icon={<ReloadOutlined />} onClick={onRetryFailed} loading={retrying} danger>Retry failed</Button>
            <Input.Search placeholder="Search by key or file name…" allowClear defaultValue={query.search}
                          aria-label="Search images" style={{ width: 260 }} onSearch={value => onChangeParams({ search: value })} />
            <Select value={query.sortBy} onChange={value => onChangeParams({ sort_by: value })}
                    aria-label="Sort by" style={{ width: 170 }} options={SORT_OPTIONS} />
            <Button
                icon={descending ? <SortDescendingOutlined /> : <SortAscendingOutlined />}
                onClick={() => onChangeParams({ sort_order: descending ? "asc" : "desc" })}
                title={descending ? "Descending" : "Ascending"}
                aria-label={descending ? "Sort descending (click for ascending)" : "Sort ascending (click for descending)"}
            />
            {data && (
                <Text style={{ fontSize: 12, color: "#94a3b8", marginLeft: "auto" }}>
                    {data.total_groups.toLocaleString()} {pluralize(data.total_groups, "group")} · {data.total_images.toLocaleString()} {pluralize(data.total_images, "image")}
                </Text>
            )}
        </div>
    );
}
