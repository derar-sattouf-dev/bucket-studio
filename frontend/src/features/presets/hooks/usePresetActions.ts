import { useState } from "react";
import { App } from "antd";
import { getErrorMessage } from "../../../api/client";
import { createPreset, deletePreset, setDefaultPreset, updatePreset } from "../../../api/presets";
import type { Preset, PresetDraft } from "../../../types/preset";

/** Admin mutations on presets; each reloads the list on success and reports errors as toasts. */
export function usePresetActions(reload: () => Promise<void>) {
    const { message } = App.useApp();
    const [saving, setSaving] = useState(false);
    const [pendingId, setPendingId] = useState<number | null>(null);

    async function attempt(task: () => Promise<unknown>, success: string, fallbackError: string): Promise<boolean> {
        try {
            await task();
            message.success(success);
            await reload();
            return true;
        } catch (error) {
            message.error(getErrorMessage(error, fallbackError));
            return false;
        }
    }

    /** Creates when `id` is null, updates otherwise. */
    async function save(id: number | null, draft: PresetDraft): Promise<boolean> {
        setSaving(true);
        const task = id === null ? () => createPreset(draft) : () => updatePreset(id, draft);
        const ok = await attempt(task, `Preset "${draft.name}" saved`, "Failed to save the preset");
        setSaving(false);
        return ok;
    }

    async function onPreset(preset: Preset, task: () => Promise<unknown>, success: string, fallbackError: string) {
        setPendingId(preset.id);
        await attempt(task, success, fallbackError);
        setPendingId(null);
    }

    const remove = (preset: Preset) =>
        onPreset(preset, () => deletePreset(preset.id), `Preset "${preset.name}" deleted`, "Failed to delete the preset");

    const makeDefault = (preset: Preset) =>
        onPreset(preset, () => setDefaultPreset(preset.id), `"${preset.name}" is now the default preset`, "Failed to set the default");

    return { saving, pendingId, save, remove, makeDefault };
}
