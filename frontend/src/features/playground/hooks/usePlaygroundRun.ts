import { useCallback, useEffect, useRef, useState } from "react";
import { getErrorMessage, isAbortError } from "../../../api/client";
import { runPlaygroundUpload, runPlaygroundUrl } from "../../../api/playground";
import type { PlaygroundRecipe, PlaygroundResult } from "../../../types/playground";
import { useObjectUrl } from "../../../hooks/useObjectUrl";
import type { PlaygroundSource } from "../types";

/** One playground run at a time: starting another (or unmounting) cancels the previous one. */
export function usePlaygroundRun() {
    const [result, setResult] = useState<PlaygroundResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [running, setRunning] = useState(false);
    const controllerRef = useRef<AbortController | null>(null);
    const [resultUrl, setResultBlob] = useObjectUrl();

    useEffect(() => () => controllerRef.current?.abort(), []);

    const run = useCallback(async (source: PlaygroundSource, recipe: PlaygroundRecipe) => {
        controllerRef.current?.abort();
        const controller = new AbortController();
        controllerRef.current = controller;
        setRunning(true);
        setError(null);
        try {
            const next = source.kind === "file"
                ? await runPlaygroundUpload(source.file, recipe, controller.signal)
                : await runPlaygroundUrl(source.url, recipe, controller.signal);
            setResult(next);
            setResultBlob(next.blob);
        } catch (e) {
            if (!isAbortError(e)) setError(getErrorMessage(e, "Processing failed"));
        } finally {
            if (controllerRef.current === controller) setRunning(false);
        }
    }, [setResultBlob]);

    const reset = useCallback(() => {
        controllerRef.current?.abort();
        setResult(null);
        setResultBlob(null);
        setError(null);
        setRunning(false);
    }, [setResultBlob]);

    return { result, resultUrl, error, running, run, reset };
}
