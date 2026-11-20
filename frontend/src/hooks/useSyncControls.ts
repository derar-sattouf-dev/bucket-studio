import { useCallback, useEffect, useState } from "react";
import { App } from "antd";
import { cancelSync, fetchSyncStatus, syncBucket } from "../api/images";
import { getErrorMessage } from "../api/client";
import type { SyncResult } from "../types/image";

const POLL_INTERVAL_MS = 4000;

/**
 * Manual S3 sync + cancel, and a poll of the scheduler's background sync state.
 * `onSynced` runs after a successful manual sync.
 */
export function useSyncControls(onSynced: (result: SyncResult) => void) {
    const { message } = App.useApp();
    const [syncing, setSyncing] = useState(false);
    const [autoSyncing, setAutoSyncing] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const poll = () => {
            fetchSyncStatus()
                .then(status => { if (!cancelled) setAutoSyncing(status.syncing); })
                .catch(() => undefined); // transient; the next poll retries
        };
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => { cancelled = true; clearInterval(id); };
    }, []);

    const sync = useCallback(async () => {
        setSyncing(true);
        try {
            onSynced(await syncBucket());
        } catch (error) {
            message.error(getErrorMessage(error, "Sync failed"));
        } finally {
            setSyncing(false);
        }
    }, [message, onSynced]);

    const cancel = useCallback(async () => {
        try {
            await cancelSync();
            message.info("Sync cancelled");
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to cancel sync"));
        }
    }, [message]);

    return { syncing, autoSyncing, sync, cancel };
}
