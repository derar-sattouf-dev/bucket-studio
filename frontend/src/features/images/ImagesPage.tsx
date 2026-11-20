import { useCallback, useMemo, useState } from "react";
import { App, Pagination, Spin } from "antd";
import { PictureOutlined } from "@ant-design/icons";
import { publishGroup } from "../../api/images";
import { BulkPublishProgress } from "../../components/BulkPublishProgress";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { SectionLoader } from "../../components/PageLoader";
import { useBulkPublish } from "../../hooks/useBulkPublish";
import { usePresets } from "../../hooks/usePresets";
import { useSyncControls } from "../../hooks/useSyncControls";
import type { GroupSelector, ImageGroup, ImageRecord, ProcessTarget, SyncResult, TaskStatus } from "../../types/image";
import { pluralize } from "../../utils/format";
import { BatchActionBar } from "./components/BatchActionBar";
import { GroupSection } from "./components/GroupSection";
import { ImageDetailDrawer } from "./components/ImageDetailDrawer";
import { ImagesEmptyState } from "./components/ImagesEmptyState";
import { ImagesToolbar } from "./components/ImagesToolbar";
import { KeyboardHint } from "./components/KeyboardHint";
import { ProcessDialog } from "./components/ProcessDialog";
import type { ImageActionHandlers, ImageBusyState } from "./components/types";
import { STATUS_HEADINGS } from "./constants";
import { useImageActions } from "./hooks/useImageActions";
import { useImageList } from "./hooks/useImageList";
import { useImageListParams } from "./hooks/useImageListParams";
import { useImageSelection } from "./hooks/useImageSelection";
import { useImageStatusStream } from "./hooks/useImageStatusStream";
import { useSelectionShortcuts } from "./hooks/useSelectionShortcuts";
import { applyTaskStatus, keysOf } from "./imageUtils";

/** Groups start collapsed once a page holds more images than this. */
const EXPAND_ALL_UP_TO = 60;

export default function ImagesPage() {
    const { message } = App.useApp();
    const { query, setParams } = useImageListParams();
    const { data, loading, error, version, reload, updateImages, loadMore, loadingMore } = useImageList(query);
    const groups = useMemo(() => data?.items ?? [], [data]);
    const selection = useImageSelection(groups, version);
    const presets = usePresets();

    const [processTarget, setProcessTarget] = useState<ProcessTarget | null>(null);
    const [detailImage, setDetailImage] = useState<ImageRecord | null>(null);
    const closeDetail = useCallback(() => setDetailImage(null), []);

    const applyStatuses = useCallback(
        (statuses: Record<string, TaskStatus>) => updateImages(image => applyTaskStatus(image, statuses[image.source_key])),
        [updateImages],
    );
    const { watch } = useImageStatusStream({ onStatuses: applyStatuses, onFinished: reload });
    const actions = useImageActions({ data, reload, updateImages, watch, clearSelection: selection.clear, closeDetail });
    // Publishing a whole group runs in the background on the server; this follows its progress.
    const refresh = useCallback(() => void reload(), [reload]);
    const bulk = useBulkPublish(refresh);
    /** The group's images under the current filters, including the ones that are not loaded. */
    const selectorOf = (group: ImageGroup): GroupSelector => ({ group: group.group, status: query.status, search: query.search });

    const onSynced = useCallback((result: SyncResult) => {
        message.success(`Sync complete: ${result.synced} new ${pluralize(result.synced, "image")}`);
        void reload();
    }, [message, reload]);
    const sync = useSyncControls(onSynced);

    const selectedKeys = selection.keys;
    useSelectionShortcuts({
        enabled: processTarget === null && detailImage === null,
        onToggleAll: selection.toggleAll,
        onProcess: selectedKeys.all.length > 0 ? () => setProcessTarget({ keys: selectedKeys.all }) : undefined,
        onClear: selection.clear,
    });

    const handlers: ImageActionHandlers = {
        onProcess: keys => { setProcessTarget({ keys }); closeDetail(); },
        onProcessGroup: group => setProcessTarget({
            group: selectorOf(group), count: group.image_count, loadedKeys: keysOf(group.images),
        }),
        onPublishGroup: group => void bulk.start(() => publishGroup(selectorOf(group))),
        onPublish: keys => void actions.publish(keys),
        onRestore: keys => void actions.restore(keys),
        onReset: keys => void actions.resetPending(keys),
        onAbort: key => void actions.abort(key),
        onSaveNotes: actions.updateNotes,
        onView: setDetailImage,
    };
    const busy = { ...actions.busy, publishing: actions.busy.publishing || bulk.busy };
    const busyState: ImageBusyState = { ...busy, aborting: actions.aborting };
    const presetName = (id: number | null) => presets.presets.find(preset => preset.id === id)?.name ?? null;

    const heading = STATUS_HEADINGS[query.status] ?? STATUS_HEADINGS[""];
    const imageCount = groups.reduce((sum, group) => sum + group.images.length, 0);

    function renderList() {
        if (!data) {
            if (loading) return <SectionLoader />;
            return error ? <LoadError message={error} onRetry={() => void reload()} /> : null;
        }
        if (groups.length === 0) {
            return (
                <ImagesEmptyState
                    filtered={Boolean(query.status || query.search)}
                    syncing={sync.syncing}
                    onSync={() => void sync.sync()}
                    onClearFilters={() => setParams({ status: "", search: "" })}
                />
            );
        }
        return (
            <Spin spinning={loading}>
                {groups.map(group => (
                    <GroupSection
                        key={group.group ?? ""}
                        group={group}
                        grouped={data.grouped}
                        loadingMore={loadingMore.has(group.group ?? "")}
                        onLoadMore={() => void loadMore(group.group, group.images.length)}
                        selected={selection.selected}
                        onSelectionChange={selection.replaceWithin}
                        handlers={handlers}
                        busy={busyState}
                        defaultExpanded={imageCount <= EXPAND_ALL_UP_TO}
                    />
                ))}
            </Spin>
        );
    }

    return (
        <PageContainer>
            <PageHeader
                icon={<PictureOutlined />} iconColor="#006A64" tint="#f0fdf4" marginBottom={20}
                title={heading.label} subtitle={heading.description}
            />

            {processTarget && (
                <ProcessDialog
                    imageCount={"keys" in processTarget ? processTarget.keys.length : processTarget.count}
                    presets={presets.presets}
                    presetsLoading={presets.loading}
                    loading={actions.busy.processing}
                    onClose={() => setProcessTarget(null)}
                    onSubmit={async options => { if (await actions.process(processTarget, options)) setProcessTarget(null); }}
                />
            )}
            <ImageDetailDrawer image={detailImage} presetName={presetName} onClose={closeDetail} handlers={handlers} busy={busyState} />

            <ImagesToolbar
                query={query}
                data={data}
                sync={{ ...sync, onSync: () => void sync.sync(), onCancel: () => void sync.cancel() }}
                retrying={actions.busy.retrying}
                onRetryFailed={() => void actions.retryAllFailed()}
                onChangeParams={setParams}
            />

            {selectedKeys.all.length > 0 ? (
                <BatchActionBar keys={selectedKeys} busy={busy} handlers={handlers} onDeselect={selection.clear} />
            ) : (
                <KeyboardHint />
            )}

            <BulkPublishProgress status={bulk.status} />

            {renderList()}

            {data && data.total_pages > 1 && (
                <div style={{ marginTop: 16, textAlign: "right" }}>
                    <Pagination
                        current={query.page}
                        // Pages count groups, or images when grouping is off; total_pages covers both.
                        total={data.total_pages * data.page_size}
                        pageSize={data.page_size}
                        onChange={page => setParams({ page: String(page) }, false)}
                        showSizeChanger={false}
                    />
                </div>
            )}
        </PageContainer>
    );
}
