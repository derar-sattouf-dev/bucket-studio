import { useState } from "react";
import { Button, Checkbox, Popconfirm, Space, Tag, Typography } from "antd";
import { CloudUploadOutlined, DownOutlined, FolderOutlined, RightOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { GROUP_PAGE_SIZE } from "../../../api/images";
import type { ImageGroup, ImageStatus } from "../../../types/image";
import { pluralize } from "../../../utils/format";
import { PUBLISH_BUTTON_STYLE, STATUS_TAG } from "../constants";
import { groupStatus, isBusy, keysOf } from "../imageUtils";
import { ImageTable } from "./ImageTable";
import { StatusTag } from "./StatusTags";
import type { ImageActionHandlers, ImageBusyState } from "./types";

const { Text } = Typography;

interface GroupSectionProps {
    group: ImageGroup;
    /** False when grouping is off: the single null group is then a plain page of images. */
    grouped: boolean;
    selected: Set<string>;
    onSelectionChange: (scope: string[], chosen: string[]) => void;
    handlers: ImageActionHandlers;
    busy: ImageBusyState;
    defaultExpanded: boolean;
    loadingMore: boolean;
    /** Fetches the group's next images. */
    onLoadMore: () => void;
}

const BOX = { border: "1px solid #e2e8f0", borderRadius: 10, background: "#fff", overflow: "hidden", marginBottom: 12 } as const;

/** Status of the loaded images (a group that is only partly loaded is summarised by that part). */
function StatusCounts({ group }: { group: ImageGroup }) {
    const status = groupStatus(group.images);
    const counts = new Map<ImageStatus, number>();
    group.images.forEach(image => counts.set(image.status, (counts.get(image.status) ?? 0) + 1));
    return (
        <Space size={4} wrap>
            <StatusTag status={status} />
            {[...counts].filter(([s]) => s !== status).map(([s, n]) => (
                <Tag key={s} color={STATUS_TAG[s].color} style={{ fontSize: 10, padding: "0 4px" }}>{n} {STATUS_TAG[s].label.toLowerCase()}</Tag>
            ))}
        </Space>
    );
}

/**
 * One folder group of the image list; images above the grouping depth form the "Ungrouped" one.
 * Only the group's first images are loaded ("Load more" fetches the next ones), while the
 * header's count and its Process / Publish buttons cover the whole group. With grouping off
 * there is no header: the images are one plain page.
 */
export function GroupSection({
    group, grouped, selected, onSelectionChange, handlers, busy, defaultExpanded, loadingMore, onLoadMore,
}: GroupSectionProps) {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const table = (
        <ImageTable images={group.images} selected={selected} onSelectionChange={onSelectionChange} handlers={handlers} busy={busy} />
    );
    if (!grouped) return <div style={BOX}>{table}</div>;

    const name = group.group ?? "Ungrouped";
    const keys = keysOf(group.images);
    const selectedCount = keys.filter(key => selected.has(key)).length;
    const remaining = Math.max(group.image_count - keys.length, 0);
    const publishable = group.publishable_count;
    const anyBusy = group.images.some(isBusy);
    const total = `${group.image_count.toLocaleString()} ${pluralize(group.image_count, "image")}`;

    return (
        <section style={BOX} aria-label={`Group ${name}`}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: "#f8fafc", flexWrap: "wrap" }}>
                <Checkbox
                    checked={selectedCount === keys.length && keys.length > 0}
                    indeterminate={selectedCount > 0 && selectedCount < keys.length}
                    onChange={event => onSelectionChange(keys, event.target.checked ? keys : [])}
                    aria-label={`Select the ${remaining > 0 ? "loaded" : "all"} images in ${name}`}
                />
                <Button type="text" size="small" onClick={() => setExpanded(v => !v)} aria-expanded={expanded}
                        aria-label={`${expanded ? "Collapse" : "Expand"} ${name}`}
                        icon={expanded ? <DownOutlined /> : <RightOutlined />} />
                <Space size={6} style={{ minWidth: 0 }}>
                    <FolderOutlined style={{ color: "#64748b" }} />
                    <Text strong style={{ fontSize: 13 }} italic={group.group === null}>{name}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{total}</Text>
                </Space>
                <StatusCounts group={group} />
                <Space size={4} style={{ marginLeft: "auto" }}>
                    <Button size="small" icon={<ThunderboltOutlined />} disabled={anyBusy} onClick={() => handlers.onProcessGroup(group)}>
                        Process
                    </Button>
                    {publishable > 0 && (
                        <Popconfirm
                            title={`Publish ${publishable.toLocaleString()} ${pluralize(publishable, "image")} of ${name}?`}
                            description="Each original is backed up, then replaced by its processed result."
                            okText="Publish" onConfirm={() => handlers.onPublishGroup(group)} disabled={anyBusy || busy.publishing}
                        >
                            <Button size="small" type="primary" icon={<CloudUploadOutlined />} style={PUBLISH_BUTTON_STYLE}
                                    loading={busy.publishing} disabled={anyBusy}>
                                Publish {publishable.toLocaleString()}
                            </Button>
                        </Popconfirm>
                    )}
                </Space>
            </div>
            {expanded && table}
            {expanded && remaining > 0 && (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, padding: "10px 14px", borderTop: "1px solid #e2e8f0" }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>Showing {keys.length.toLocaleString()} of {total}</Text>
                    <Button size="small" loading={loadingMore} onClick={onLoadMore}>
                        Load {Math.min(remaining, GROUP_PAGE_SIZE)} more
                    </Button>
                </div>
            )}
        </section>
    );
}
