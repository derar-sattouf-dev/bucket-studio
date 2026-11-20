import { useState } from "react";
import { App, Button, Empty, Input, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined, SearchOutlined, WarningOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../api/client";
import { fetchFailedImages, retryFailed } from "../../api/images";
import { KeyCell } from "../../components/KeyCell";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { usePagedImages } from "../../hooks/usePagedImages";
import type { ImageRecord } from "../../types/image";
import { formatDateTime, pluralize } from "../../utils/format";

const { Text } = Typography;

const PAGE_SIZE = 20;

const count = (n: number) => `${n.toLocaleString()} ${pluralize(n, "image")}`;

const columns: ColumnsType<ImageRecord> = [
    { title: "Image", render: (_, row) => <KeyCell objectKey={row.source_key} /> },
    {
        title: "Error",
        dataIndex: "error_message",
        render: (error: string | null) => (
            <Tooltip title={error}>
                <Text type="danger" style={{ fontSize: 12, display: "block" }} ellipsis>{error ?? "—"}</Text>
            </Tooltip>
        ),
    },
    {
        title: "Retries",
        dataIndex: "retry_count",
        width: 90,
        render: (n: number) => <Tag color={n >= 3 ? "red" : n >= 1 ? "orange" : "default"}>{n}</Tag>,
    },
    {
        title: "Last attempt",
        dataIndex: "updated_at",
        width: 170,
        render: (value: string) => <Text type="secondary" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{formatDateTime(value)}</Text>,
    },
];

/** Every image whose processing failed, with its error, and a bulk retry. */
export default function FailedPage() {
    const { message } = App.useApp();
    const list = usePagedImages(fetchFailedImages, PAGE_SIZE, "Failed to load failed images");
    const { reload } = list;
    const [retrying, setRetrying] = useState(false);

    async function handleRetryAll() {
        setRetrying(true);
        try {
            const { queued, skipped_max_retries: atLimit, skipped_other: other } = await retryFailed();
            message.success(`Queued ${count(queued)} for another try`);
            if (atLimit) message.info(`${count(atLimit)} reached the retry limit and were skipped`);
            if (other) message.info(`${count(other)} skipped: already being processed or no longer a source image`);
            await reload();
        } catch (e) {
            message.error(getErrorMessage(e, "Failed to retry"));
        } finally {
            setRetrying(false);
        }
    }

    // With a search, `total` counts the matches only; "Retry all" always takes every failure.
    const nothingFailed = list.total === 0 && !list.search;
    const subtitle = list.search ? `${count(list.total)} matching “${list.search}”` : `${count(list.total)} failed processing`;

    if (list.error && !list.loaded) return <PageContainer><LoadError message={list.error} onRetry={() => void reload()} /></PageContainer>;

    return (
        <PageContainer>
            <PageHeader
                icon={<WarningOutlined />} iconColor="#BA1A1A" tint="#fff1f0"
                title="Failures" subtitle={subtitle}
                extra={
                    <Space>
                        <Button icon={<ReloadOutlined />} onClick={() => void reload()}>Refresh</Button>
                        <Button type="primary" danger icon={<ReloadOutlined />} loading={retrying}
                                onClick={() => void handleRetryAll()} disabled={nothingFailed}>
                            {list.search ? "Retry all" : `Retry all (${list.total.toLocaleString()})`}
                        </Button>
                    </Space>
                }
            />

            <Input prefix={<SearchOutlined />} placeholder="Filter by key or error…" aria-label="Filter by key or error"
                   value={list.searchInput} maxLength={200} onChange={e => list.setSearchInput(e.target.value)}
                   style={{ marginBottom: 16, maxWidth: 400 }} allowClear />

            <Table<ImageRecord>
                dataSource={list.items}
                columns={columns}
                rowKey="id"
                tableLayout="fixed"
                loading={list.loading}
                size="small"
                pagination={{
                    current: list.page, pageSize: list.pageSize, total: list.total, onChange: list.setPage,
                    showSizeChanger: false, showTotal: total => count(total), hideOnSinglePage: true,
                }}
                locale={{ emptyText: <Empty description="No failed images. Nice." /> }}
            />
        </PageContainer>
    );
}
