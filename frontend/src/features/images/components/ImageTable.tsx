import { Button, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { EyeOutlined } from "@ant-design/icons";
import { EngineTag } from "../../../components/EngineTag";
import type { ImageRecord } from "../../../types/image";
import { formatBytes } from "../../../utils/format";
import { toBrowserUrl } from "../../../utils/storageUrl";
import { dimensionsLabel, displayStatus, fileName, keysOf, parseTags } from "../imageUtils";
import { ImageActionButtons } from "./ImageActionButtons";
import { LabeledThumb } from "./LabeledThumb";
import { StatusTag } from "./StatusTags";
import type { ImageActionHandlers, ImageBusyState } from "./types";

const { Text } = Typography;

interface ImageTableProps {
    images: ImageRecord[];
    selected: Set<string>;
    /** Within these images, select exactly `chosen`. */
    onSelectionChange: (scope: string[], chosen: string[]) => void;
    handlers: ImageActionHandlers;
    busy: ImageBusyState;
}

function buildColumns(handlers: ImageActionHandlers, busy: ImageBusyState): ColumnsType<ImageRecord> {
    return [
        {
            title: "Preview",
            width: 132,
            render: (_, image) => (
                <Space size={6}>
                    <LabeledThumb label="Original" url={toBrowserUrl(image.is_published ? image.backup_url : image.source_url)} size={48} />
                    <LabeledThumb label="Result" url={toBrowserUrl(image.is_published ? image.source_url : image.processed_url)} size={48} checkerboard />
                </Space>
            ),
        },
        {
            title: "File",
            render: (_, image) => (
                <div style={{ minWidth: 0, overflow: "hidden" }}>
                    <Tooltip title={image.source_key}>
                        <Text strong ellipsis style={{ fontSize: 13, display: "block" }}>{fileName(image.source_key)}</Text>
                    </Tooltip>
                    <Space size={2} wrap>
                        {parseTags(image.tags).map(tag => <Tag key={tag} color="geekblue" style={{ fontSize: 10 }}>{tag}</Tag>)}
                    </Space>
                </div>
            ),
        },
        {
            title: "Status",
            width: 170,
            render: (_, image) => (
                <Space size={2} wrap>
                    <Tooltip title={image.status === "failed" ? image.error_message : undefined}>
                        <StatusTag status={displayStatus(image)} />
                    </Tooltip>
                    {image.status === "processed" && <EngineTag processedBy={image.processed_by} />}
                </Space>
            ),
        },
        {
            title: "Size",
            width: 160,
            render: (_, image) => (
                <div style={{ fontSize: 12, lineHeight: 1.4, whiteSpace: "nowrap" }}>
                    <div>{formatBytes(image.source_size)}{image.processed_size ? ` → ${formatBytes(image.processed_size)}` : ""}</div>
                    <Text type="secondary" style={{ fontSize: 11 }}>{dimensionsLabel(image)}</Text>
                </div>
            ),
        },
        {
            title: "Actions",
            width: 290,
            render: (_, image) => (
                <Space size={4} wrap>
                    <Button size="small" icon={<EyeOutlined />} onClick={() => handlers.onView(image)}
                            aria-label={`Details of ${fileName(image.source_key)}`}>
                        Details
                    </Button>
                    <ImageActionButtons image={image} variant="row" handlers={handlers} busy={busy} />
                </Space>
            ),
        },
    ];
}

/** The images of one group, with per-row selection and actions. */
export function ImageTable({ images, selected, onSelectionChange, handlers, busy }: ImageTableProps) {
    const scope = keysOf(images);
    return (
        <Table<ImageRecord>
            rowKey="source_key"
            dataSource={images}
            columns={buildColumns(handlers, busy)}
            pagination={false}
            size="small"
            // Fixed layout: long file names truncate instead of stretching the table.
            tableLayout="fixed"
            scroll={{ x: 860 }}
            rowSelection={{
                selectedRowKeys: scope.filter(key => selected.has(key)),
                onChange: keys => onSelectionChange(scope, keys.map(String)),
                getCheckboxProps: image => ({ title: `Select ${fileName(image.source_key)}` }),
            }}
        />
    );
}
