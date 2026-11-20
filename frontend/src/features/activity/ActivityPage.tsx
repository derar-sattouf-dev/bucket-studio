import { useCallback, useEffect, useRef, useState } from "react";
import { App, Button, Empty, Input, Select, Tag, Timeline, Typography } from "antd";
import { HistoryOutlined, ReloadOutlined } from "@ant-design/icons";
import { fetchActivity } from "../../api/activity";
import { getErrorMessage } from "../../api/client";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { SectionLoader } from "../../components/PageLoader";
import { EVENT_FILTER_OPTIONS, EVENT_META, UNKNOWN_EVENT_COLOR } from "../../constants/activityEvents";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import type { ActivityItem } from "../../types/activity";

const { Text } = Typography;

const LIMIT_OPTIONS = [20, 50, 100, 200].map(value => ({ value, label: `Last ${value}` }));
const SEARCH_DEBOUNCE_MS = 300;

export default function ActivityPage() {
    const { message } = App.useApp();
    const [items, setItems] = useState<ActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [limit, setLimit] = useState(50);
    const [filter, setFilter] = useState("all");
    const [searchText, setSearchText] = useState("");
    const search = useDebouncedValue(searchText, SEARCH_DEBOUNCE_MS);
    const [error, setError] = useState<string | null>(null);
    const latestRequest = useRef(0);

    const load = useCallback(async () => {
        // Only the latest request is applied: a slow earlier response must not overwrite a newer one.
        const request = ++latestRequest.current;
        setLoading(true);
        try {
            const result = await fetchActivity(limit, search);
            if (request !== latestRequest.current) return;
            setItems(result);
            setError(null);
        } catch (e) {
            if (request !== latestRequest.current) return;
            const text = getErrorMessage(e, "Failed to load activity");
            setError(text);
            message.error(text);
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
    }, [limit, search, message]);

    useEffect(() => { void load(); }, [load]);

    const filtered = filter === "all" ? items : items.filter(item => item.event_type === filter);

    return (
        <PageContainer>
            <PageHeader
                icon={<HistoryOutlined />} iconColor="#1677ff" tint="#f0f9ff"
                title="Activity" subtitle="Everything that happened: syncs, imports, processing, publishing and sign-ins"
                extra={<Button icon={<ReloadOutlined />} onClick={() => void load()}>Refresh</Button>}
            />

            <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
                <Select value={filter} onChange={setFilter} style={{ width: 200 }} options={EVENT_FILTER_OPTIONS} aria-label="Event type" />
                <Input.Search placeholder="Search events…" aria-label="Search events" allowClear style={{ width: 240 }}
                              value={searchText} onChange={e => setSearchText(e.target.value)} onSearch={() => void load()} />
                <Select value={limit} onChange={setLimit} style={{ width: 120 }} options={LIMIT_OPTIONS} aria-label="Number of events" />
            </div>

            {loading ? (
                <SectionLoader />
            ) : error && items.length === 0 ? (
                <LoadError message={error} onRetry={() => void load()} />
            ) : filtered.length === 0 ? (
                <Empty description={items.length === 0 ? "No activity yet." : "No events match these filters."} />
            ) : (
                <Timeline
                    items={filtered.map(item => {
                        const meta = EVENT_META[item.event_type];
                        return {
                            color: meta?.color ?? UNKNOWN_EVENT_COLOR,
                            dot: meta?.icon,
                            children: (
                                <div style={{ paddingBottom: 8 }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                                        <Tag color={meta?.color ?? "default"} style={{ fontSize: 11 }}>{meta?.label ?? item.event_type}</Tag>
                                        {item.username && <Tag color="default" style={{ fontSize: 11 }}>@{item.username}</Tag>}
                                        <Text type="secondary" style={{ fontSize: 12 }}>{new Date(item.created_at).toLocaleString()}</Text>
                                    </div>
                                    <Text style={{ fontSize: 13 }}>{item.message}</Text>
                                </div>
                            ),
                        };
                    })}
                />
            )}
        </PageContainer>
    );
}
