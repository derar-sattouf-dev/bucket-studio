import { useState } from "react";
import { App } from "antd";
import { getErrorMessage } from "../../../api/client";
import {
    abortImage, processGroup, processImages, publishImages, resetToPending, restoreImages, retryFailed, saveNotes,
} from "../../../api/images";
import type { ImagePage, ImageRecord, KeyResult, ProcessOptions, ProcessTarget } from "../../../types/image";
import { pluralize } from "../../../utils/format";
import { summarizeResults } from "../../../utils/keyResults";

export type BusyFlag = "processing" | "publishing" | "restoring" | "resetting" | "retrying";

const IDLE: Record<BusyFlag, boolean> = {
    processing: false, publishing: false, restoring: false, resetting: false, retrying: false,
};

interface Dependencies {
    data: ImagePage | null;
    reload: () => Promise<void>;
    updateImages: (update: (image: ImageRecord) => ImageRecord) => void;
    /** Start streaming status for keys that were just queued. */
    watch: (keys: string[]) => void;
    clearSelection: () => void;
    closeDetail: () => void;
}

const images = (count: number) => `${count.toLocaleString()} ${pluralize(count, "image")}`;

/** Every mutation on the Images page, with its loading flag and toast. */
export function useImageActions({ data, reload, updateImages, watch, clearSelection, closeDetail }: Dependencies) {
    const { message } = App.useApp();
    const [busy, setBusy] = useState(IDLE);
    const [aborting, setAborting] = useState<Set<string>>(new Set());

    async function run(flag: BusyFlag, task: () => Promise<void>): Promise<boolean> {
        setBusy(prev => ({ ...prev, [flag]: true }));
        try {
            await task();
            return true;
        } catch (error) {
            message.error(getErrorMessage(error));
            return false;
        } finally {
            setBusy(prev => ({ ...prev, [flag]: false }));
        }
    }

    /** Success toast plus a warning naming the first per-key error, if any. */
    function reportResults(results: KeyResult[], verb: string) {
        const { succeeded, failed } = summarizeResults(results);
        if (succeeded > 0) message.success(`${verb} ${images(succeeded)}`);
        if (failed.length > 0) {
            message.warning(`${images(failed.length)} could not be ${verb.toLowerCase()}: ${failed[0].error ?? "unknown error"}`);
        }
    }

    function afterChange() {
        clearSelection();
        closeDetail();
        void reload();
    }

    /** Queues chosen images, or a whole group: the server then collects the group's keys itself. */
    const process = (target: ProcessTarget, options: ProcessOptions) => run("processing", async () => {
        if ("keys" in target) {
            await processImages({ keys: target.keys, ...options });
            message.success(`Queued ${images(target.keys.length)} for processing`);
            watch(target.keys);
        } else {
            const { queued, skipped_busy: skipped } = await processGroup(target.group, options);
            message.success(`Queued ${images(queued)} for processing`);
            if (skipped > 0) message.info(`${images(skipped)} already being processed`);
            watch(target.loadedKeys);
        }
        clearSelection();
        void reload();
    });

    const publish = (keys: string[]) => run("publishing", async () => {
        const { results } = await publishImages(keys);
        reportResults(results, "Published");
        afterChange();
    });

    const restore = (keys: string[]) => run("restoring", async () => {
        const { results } = await restoreImages(keys);
        reportResults(results, "Restored");
        afterChange();
    });

    const resetPending = (keys: string[]) => run("resetting", async () => {
        const { reset } = await resetToPending(keys);
        message.success(`Reset ${images(reset)} to pending`);
        afterChange();
    });

    const retryAllFailed = () => run("retrying", async () => {
        const failedKeys = (data?.items ?? [])
            .flatMap(group => group.images)
            .filter(image => image.status === "failed")
            .map(image => image.source_key);
        const result = await retryFailed();
        if (result.queued === 0) {
            const reasons = [
                result.skipped_max_retries > 0 && `${images(result.skipped_max_retries)} reached the retry limit`,
                result.skipped_other > 0 && `${images(result.skipped_other)} already being processed or no longer a source image`,
            ].filter(Boolean);
            message.warning(reasons.length > 0 ? `Nothing to retry: ${reasons.join(", ")}` : "Nothing to retry");
        } else {
            message.success(`Queued ${images(result.queued)} for another try`);
            watch(failedKeys);
        }
        void reload();
    });

    async function abort(key: string) {
        setAborting(prev => new Set(prev).add(key));
        try {
            await abortImage(key);
            message.success("Stopped");
            void reload();
        } catch (error) {
            message.error(getErrorMessage(error));
        } finally {
            setAborting(prev => {
                const next = new Set(prev);
                next.delete(key);
                return next;
            });
        }
    }

    async function updateNotes(sourceKey: string, notes: string | null, tags: string | null) {
        try {
            await saveNotes(sourceKey, notes, tags);
            updateImages(image => (image.source_key === sourceKey ? { ...image, notes, tags } : image));
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to save notes"));
        }
    }

    return { busy, aborting, process, publish, restore, resetPending, retryAllFailed, abort, updateNotes };
}
