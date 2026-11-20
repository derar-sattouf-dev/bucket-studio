import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { fetchPresets } from "../api/presets";
import type { Preset } from "../types/preset";

/** The preset list with loading/error state; `defaultPreset` is the one marked `is_default`. */
export function usePresets() {
    const [presets, setPresets] = useState<Preset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            setPresets(await fetchPresets());
            setError(null);
        } catch (e) {
            setError(getErrorMessage(e, "Failed to load presets"));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void reload(); }, [reload]);

    const defaultPreset = presets.find(preset => preset.is_default) ?? null;
    return { presets, loading, error, reload, defaultPreset };
}
