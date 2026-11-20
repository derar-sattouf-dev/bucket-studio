import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Popconfirm, Space, Typography } from "antd";
import { PlayCircleOutlined, ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../api/client";
import { deleteJob, fetchJobs, skipCurrentImage, startJob, stopJob } from "../../api/jobs";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { useAuth } from "../../auth/useAuth";
import { usePresets } from "../../hooks/usePresets";
import { TERMINAL_JOB_STATUSES, type Job, type StartJobRequest } from "../../types/job";
import { BatchHistoryTable } from "./components/BatchHistoryTable";
import { JobCard } from "./components/JobCard";
import { RunningJobBanner } from "./components/RunningJobBanner";
import { StartJobCard } from "./components/StartJobCard";
import { StartJobModal } from "./components/StartJobModal";
import { useJobStream } from "./hooks/useJobStream";

const { Text } = Typography;

/** Pending or running: shown in the banner and followed live. */
const isActive = (job: Job) => !TERMINAL_JOB_STATUSES.includes(job.status);

export default function JobsPage() {
    const { isAdmin } = useAuth();
    const presets = usePresets();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [activeJobId, setActiveJobId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [startModalOpen, setStartModalOpen] = useState(false);

    const upsertJob = useCallback((job: Job) => {
        setJobs(prev => {
            const index = prev.findIndex(j => j.job_id === job.job_id);
            if (index === -1) return [job, ...prev];
            const next = [...prev];
            next[index] = job;
            return next;
        });
    }, []);

    const refresh = useCallback(async () => {
        try {
            setJobs(await fetchJobs());
        } catch (e) {
            setError(getErrorMessage(e, "Failed to load jobs"));
        }
    }, []);

    useEffect(() => {
        fetchJobs()
            .then(all => {
                setJobs(all);
                const active = all.find(isActive);
                if (active) setActiveJobId(active.job_id);
            })
            .catch(e => setError(getErrorMessage(e, "Failed to load jobs")));
    }, []);

    useJobStream(activeJobId, upsertJob);

    /** Runs a job action, surfacing failures in the error banner. */
    async function attempt(action: () => Promise<void>) {
        setError(null);
        try {
            await action();
        } catch (e) {
            setError(getErrorMessage(e));
        }
    }

    async function handleStart(request: StartJobRequest) {
        setStartModalOpen(false);
        setLoading(true);
        await attempt(async () => {
            const job = await startJob(request);
            upsertJob(job);
            setActiveJobId(job.job_id);
        });
        setLoading(false);
    }

    const handleStop = (jobId: string) => attempt(async () => upsertJob(await stopJob(jobId)));
    const handleSkip = (jobId: string) => attempt(async () => upsertJob(await skipCurrentImage(jobId)));
    const handleDelete = (jobId: string) => attempt(async () => {
        await deleteJob(jobId);
        setJobs(prev => prev.filter(job => job.job_id !== jobId));
    });

    const runningJob = jobs.find(isActive);
    const finishedJobs = jobs.filter(job => !isActive(job));

    return (
        <PageContainer>
            {startModalOpen && (
                <StartJobModal
                    presets={presets.presets} presetsLoading={presets.loading} canOverwrite={isAdmin} loading={loading}
                    onConfirm={request => void handleStart(request)} onCancel={() => setStartModalOpen(false)}
                />
            )}
            {error && (
                <Alert type="error" title={error} closable={{ onClose: () => setError(null) }} style={{ marginBottom: 16 }} />
            )}

            <PageHeader
                icon={<ThunderboltOutlined />} iconColor="#1677ff" tint="#f0f5ff"
                title="Batch jobs" subtitle="Process every pending image with a preset, and follow the progress live"
                extra={
                    <Space>
                        <Button icon={<ReloadOutlined />} onClick={() => void refresh()}>Refresh</Button>
                        {!runningJob && (
                            <Button type="primary" icon={<PlayCircleOutlined />} loading={loading}
                                    onClick={() => setStartModalOpen(true)}>
                                Start batch
                            </Button>
                        )}
                    </Space>
                }
            />

            {runningJob
                ? <RunningJobBanner job={runningJob} onStop={handleStop} onSkip={handleSkip} />
                : <StartJobCard loading={loading} onStart={() => setStartModalOpen(true)} />}

            {finishedJobs.length > 0 && (
                <>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                        <Text strong style={{ fontSize: 13 }}>This session</Text>
                        <Popconfirm
                            title="Delete all finished jobs?"
                            onConfirm={() => finishedJobs.forEach(job => void handleDelete(job.job_id))}
                            okText="Clear all" okButtonProps={{ danger: true }}
                        >
                            <Button size="small" type="link" danger>Clear all</Button>
                        </Popconfirm>
                    </div>
                    {finishedJobs.map(job => <JobCard key={job.job_id} job={job} onDelete={handleDelete} />)}
                </>
            )}

            <BatchHistoryTable />
        </PageContainer>
    );
}
