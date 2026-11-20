import { useCallback, useEffect, useRef, useState } from "react";
import { App } from "antd";
import { ApiError, getErrorMessage } from "../api/client";
import { fetchBulkPublishStatus } from "../api/images";
import type { BulkPublishStatus } from "../types/image";
import { pluralize } from "../utils/format";

const POLL_INTERVAL_MS = 2000;

const images = (count: number) => `${count.toLocaleString()} ${pluralize(count, "image")}`;

/**
 * The background bulk publish ("publish all", or one whole group): starts it, polls its
 * progress while it runs and calls `onFinished` once it is done. A run that is already in
 * progress (started on another page, or before a reload) is picked up on mount.
 */
export function useBulkPublish(onFinished: () => void) {
    const { message } = App.useApp();
    const [status, setStatus] = useState<BulkPublishStatus | null>(null);
    const [starting, setStarting] = useState(false);
    const running = status?.running ?? false;

    const finished = useRef(onFinished);
    useEffect(() => { finished.current = onFinished; }, [onFinished]);

    useEffect(() => {
        let cancelled = false;
        fetchBulkPublishStatus().then(
            current => { if (!cancelled && current.running) setStatus(current); },
            () => undefined,
        );
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        if (!running) return;
        let stopped = false;
        let timer = 0;

        async function poll() {
            try {
                const next = await fetchBulkPublishStatus();
                if (stopped) return;
                setStatus(next);
                if (!next.running) {
                    if (next.published > 0) message.success(`Published ${images(next.published)}`);
                    if (next.failed > 0) {
                        message.warning(`${images(next.failed)} could not be published: ${next.errors[0]?.error ?? "unknown error"}`);
                    }
                    finished.current();
                    return;
                }
            } catch {
                // A failed poll is not the end of the run: try again.
            }
            if (!stopped) timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
        }

        timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
        return () => {
            stopped = true;
            window.clearTimeout(timer);
        };
    }, [running, message]);

    /** `request` is the API call that starts the run (`publishAll`, or `publishGroup` for one group). */
    const start = useCallback(async (request: () => Promise<{ total: number }>) => {
        setStarting(true);
        try {
            const { total } = await request();
            if (total === 0) {
                message.info("Nothing to publish");
                finished.current();
                return;
            }
            setStatus({ running: true, total, done: 0, published: 0, failed: 0, started_at: null, finished_at: null, errors: [] });
        } catch (error) {
            message.error(getErrorMessage(error, "Publishing failed"));
            // 409: another run is in progress; show that one instead.
            if (error instanceof ApiError && error.status === 409) {
                await fetchBulkPublishStatus().then(setStatus, () => undefined);
            }
        } finally {
            setStarting(false);
        }
    }, [message]);

    return { status: running ? status : null, busy: starting || running, start };
}
