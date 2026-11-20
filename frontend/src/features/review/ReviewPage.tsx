import { useCallback, useState } from "react";
import { App, Button, Empty, Image, Input, Popconfirm, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { CloudUploadOutlined, EyeOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../../api/client";
import { fetchReviewQueue, publishAll, publishImages } from "../../api/images";
import { BulkPublishProgress } from "../../components/BulkPublishProgress";
import { KeyCell } from "../../components/KeyCell";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { useBulkPublish } from "../../hooks/useBulkPublish";
import { usePagedImages } from "../../hooks/usePagedImages";
import type { ImageRecord, KeyResult } from "../../types/image";
import { formatBytes, formatDateTime, pluralize } from "../../utils/format";
import { summarizeResults } from "../../utils/keyResults";
import { CHECKERBOARD, IMAGE_FALLBACK, toBrowserUrl } from "../../utils/storageUrl";
import { EngineTag } from "../../components/EngineTag";

const { Text } = Typography;

const PAGE_SIZE = 30;

const count = (n: number) => `${n.toLocaleString()} ${pluralize(n, "image")}`;

function Thumb({ url, alt, checkerboard }: { url: string | null; alt: string; checkerboard?: boolean }) {
    return (
        <Image src={toBrowserUrl(url) ?? undefined} alt={alt} width={72} height={72} fallback={IMAGE_FALLBACK}
               loading="lazy" decoding="async"
               style={{ objectFit: "contain", borderRadius: 6, border: "1px solid #e2e8f0", background: checkerboard ? CHECKERBOARD : "#fff" }} />
    );
}

/** Processed images waiting to be published: compare, then publish one, some or all. */
export default function ReviewPage() {
    const { message } = App.useApp();
    const navigate = useNavigate();
    const list = usePagedImages(fetchReviewQueue, PAGE_SIZE, "Failed to load the review queue");
    const { reload } = list;
    const [selected, setSelected] = useState<string[]>([]);
    const [publishingSome, setPublishingSome] = useState(false);

    const afterPublish = useCallback(() => {
        setSelected([]);
        void reload();
    }, [reload]);
    // "Publish all" runs in the background on the server; this follows its progress.
    const bulk = useBulkPublish(afterPublish);
    const publishing = publishingSome || bulk.busy;

    async function publish(request: () => Promise<{ results: KeyResult[] }>) {
        setPublishingSome(true);
        try {
            const { succeeded, failed } = summarizeResults((await request()).results);
            if (succeeded) message.success(`Published ${count(succeeded)}`);
            if (failed.length) message.warning(`${count(failed.length)} not published: ${failed[0].error ?? "unknown error"}`);
            setSelected([]);
            await reload();
        } catch (e) {
            message.error(getErrorMessage(e, "Publishing failed"));
        } finally {
            setPublishingSome(false);
        }
    }

    // With a search, `total` counts the matches only; "Publish all" always takes the whole queue.
    const queueIsEmpty = list.total === 0 && !list.search;
    const subtitle = list.search
        ? `${count(list.total)} matching “${list.search}”. Publishing backs up each original first.`
        : `${count(list.total)} processed and waiting to be published. Publishing backs up each original first.`;

    const columns: ColumnsType<ImageRecord> = [
        {
            title: "Before / after",
            width: 172,
            render: (_, row) => (
                <Image.PreviewGroup>
                    <Space size={6}>
                        <Thumb url={row.source_url} alt="Original" />
                        <Thumb url={row.processed_url} alt="Result" checkerboard />
                    </Space>
                </Image.PreviewGroup>
            ),
        },
        { title: "Image", render: (_, row) => <KeyCell objectKey={row.source_key} /> },
        {
            title: "Size",
            width: 170,
            render: (_, row) => (
                <Text style={{ fontSize: 12, whiteSpace: "nowrap" }}>{formatBytes(row.source_size)} → {formatBytes(row.processed_size)}</Text>
            ),
        },
        { title: "Engine", width: 90, render: (_, row) => <EngineTag processedBy={row.processed_by} /> },
        {
            title: "Processed",
            dataIndex: "processed_at",
            width: 170,
            render: (value: string | null) => (
                <Text type="secondary" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{formatDateTime(value)}</Text>
            ),
        },
        {
            title: <span className="sr-only">Actions</span>,
            width: 112,
            render: (_, row) => (
                <Button size="small" type="primary" icon={<CloudUploadOutlined />} loading={publishing}
                        onClick={() => void publish(() => publishImages([row.source_key]))}>
                    Publish
                </Button>
            ),
        },
    ];

    if (list.error && !list.loaded) return <PageContainer><LoadError message={list.error} onRetry={() => void reload()} /></PageContainer>;

    return (
        <PageContainer>
            <PageHeader
                icon={<EyeOutlined />} iconColor="#006A64" tint="#f0fdf4"
                title="Review"
                subtitle={subtitle}
                extra={
                    <Space wrap>
                        <Button icon={<ReloadOutlined />} onClick={() => void reload()}>Refresh</Button>
                        {selected.length > 0 && (
                            <Button type="primary" icon={<CloudUploadOutlined />} loading={publishing}
                                    onClick={() => void publish(() => publishImages(selected))}>
                                Publish selected ({selected.length})
                            </Button>
                        )}
                        <Popconfirm
                            title={list.search ? "Publish every processed image?" : `Publish all ${count(list.total)}?`}
                            description="Every original is backed up, then replaced by its processed result."
                            okText="Publish all" onConfirm={() => void bulk.start(publishAll)} disabled={queueIsEmpty || publishing}
                        >
                            <Button type="primary" icon={<CloudUploadOutlined />} loading={bulk.busy} disabled={queueIsEmpty || publishing}>
                                Publish all
                            </Button>
                        </Popconfirm>
                    </Space>
                }
            />

            <BulkPublishProgress status={bulk.status} />

            <Input prefix={<SearchOutlined />} placeholder="Filter by key…" aria-label="Filter by key" value={list.searchInput} allowClear
                   maxLength={200} onChange={e => list.setSearchInput(e.target.value)} style={{ marginBottom: 16, maxWidth: 400 }} />

            <Table<ImageRecord>
                dataSource={list.items}
                columns={columns}
                rowKey="source_key"
                // Fixed layout: long file names truncate instead of pushing the actions off screen.
                tableLayout="fixed"
                scroll={{ x: 900 }}
                loading={list.loading}
                size="small"
                pagination={{
                    current: list.page, pageSize: list.pageSize, total: list.total, onChange: list.setPage,
                    showSizeChanger: false, showTotal: total => count(total), hideOnSinglePage: true,
                }}
                // The selection survives paging: it holds keys, not rows of the current page.
                rowSelection={{ selectedRowKeys: selected, preserveSelectedRowKeys: true, onChange: keys => setSelected(keys.map(String)) }}
                locale={{
                    emptyText: (
                        <Empty description="Nothing to review. Processed images appear here until they are published.">
                            <Button onClick={() => navigate("/images?status=pending")}>See pending images</Button>
                        </Empty>
                    ),
                }}
            />
        </PageContainer>
    );
}
