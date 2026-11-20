import { useCallback, useEffect, useState } from "react";
import { Button, Col, Row, Space } from "antd";
import { HomeOutlined, ReloadOutlined } from "@ant-design/icons";
import { fetchActivity } from "../../api/activity";
import { getErrorMessage } from "../../api/client";
import { publishAll } from "../../api/images";
import { fetchPipelineStats } from "../../api/stats";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { SectionLoader } from "../../components/PageLoader";
import { useBulkPublish } from "../../hooks/useBulkPublish";
import { useSyncControls } from "../../hooks/useSyncControls";
import type { ActivityItem } from "../../types/activity";
import type { PipelineStats } from "../../types/stats";
import { GettingStartedCard } from "./components/GettingStartedCard";
import { QuickActionsCard } from "./components/QuickActionsCard";
import { RecentActivityCard } from "./components/RecentActivityCard";
import { StatCards } from "./components/StatCards";
import { SyncButtons } from "./components/SyncButtons";

export default function DashboardPage() {
    const [stats, setStats] = useState<PipelineStats | null>(null);
    const [activity, setActivity] = useState<ActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const [pipeline, recent] = await Promise.all([fetchPipelineStats(), fetchActivity(20)]);
            setStats(pipeline);
            setActivity(recent);
            setError(null);
        } catch (e) {
            setError(getErrorMessage(e, "Failed to load the dashboard"));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void load(); }, [load]);

    const sync = useSyncControls(load);
    const syncState = { ...sync, onSync: () => void sync.sync(), onCancel: () => void sync.cancel() };

    // "Publish all" runs in the background on the server; this follows it and reloads at the end.
    const refresh = useCallback(() => void load(), [load]);
    const bulk = useBulkPublish(refresh);

    if (loading) return <SectionLoader />;
    if (!stats) return <PageContainer><LoadError message={error ?? "No data"} onRetry={() => void load()} /></PageContainer>;

    // `processed` includes published images: publishing does not change the status.
    const awaitingReview = Math.max(stats.processed - stats.published, 0);
    const isEmpty = stats.total === 0;

    return (
        <PageContainer>
            <PageHeader
                icon={<HomeOutlined />} iconColor="#006A64" tint="#f0fdf4"
                title="Dashboard" subtitle="Where your images are in the pipeline"
                extra={
                    <Space size={8} wrap>
                        <Button icon={<ReloadOutlined />} onClick={() => void load()}>Refresh</Button>
                        <SyncButtons {...syncState} />
                    </Space>
                }
            />

            {isEmpty
                ? <GettingStartedCard syncing={sync.syncing} onSync={syncState.onSync} />
                : <StatCards stats={stats} />}

            <Row gutter={[16, 16]}>
                {!isEmpty && (
                    <Col xs={24} lg={8}>
                        <QuickActionsCard
                            stats={stats} awaitingReview={awaitingReview} sync={syncState}
                            publishing={bulk.busy} publishStatus={bulk.status} onPublishAll={() => void bulk.start(publishAll)}
                        />
                    </Col>
                )}
                <Col xs={24} lg={isEmpty ? 24 : 16}>
                    <RecentActivityCard items={activity} />
                </Col>
            </Row>
        </PageContainer>
    );
}
