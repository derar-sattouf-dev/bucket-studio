import { useCallback, useEffect, useState } from "react";
import { streamImageStatuses } from "../../../api/images";
import type { TaskStatus } from "../../../types/image";

interface StreamHandlers {
    onStatuses: (statuses: Record<string, TaskStatus>) => void;
    /** Called once when every watched key has finished, or the stream fails. */
    onFinished: () => void;
}

/**
 * Watches per-image processing status over SSE while any image is being processed.
 * Adding keys restarts the stream with the union of all watched keys.
 */
export function useImageStatusStream({ onStatuses, onFinished }: StreamHandlers) {
    const [watchedKeys, setWatchedKeys] = useState<string[]>([]);

    const watch = useCallback((keys: string[]) => {
        setWatchedKeys(prev => [...new Set([...prev, ...keys])]);
    }, []);

    useEffect(() => {
        if (watchedKeys.length === 0) return;
        const controller = new AbortController();
        let finished = false;
        const finish = () => {
            if (finished || controller.signal.aborted) return;
            finished = true;
            setWatchedKeys([]);
            onFinished();
        };

        streamImageStatuses(watchedKeys, event => {
            onStatuses(event.statuses);
            if (event.all_done) finish();
        }, controller.signal)
            // A stream that ends without `all_done`, or errors, falls back to a plain reload.
            .then(finish, finish);

        return () => controller.abort();
    }, [watchedKeys, onStatuses, onFinished]);

    return { watch };
}
