import type { Preset, PresetDraft } from "../types/preset";
import { apiFetch, apiJson } from "./client";

// Reading is open to every signed-in user; every change is admin only.

export function fetchPresets(): Promise<Preset[]> {
    return apiJson<Preset[]>("/presets/");
}

export function createPreset(draft: PresetDraft): Promise<Preset> {
    return apiJson<Preset>("/presets/", { method: "POST", json: draft });
}

export function updatePreset(id: number, patch: Partial<PresetDraft>): Promise<Preset> {
    return apiJson<Preset>(`/presets/${id}`, { method: "PATCH", json: patch });
}

/** Fails with 409 for the default preset. */
export async function deletePreset(id: number): Promise<void> {
    await apiFetch(`/presets/${id}`, { method: "DELETE" });
}

export function setDefaultPreset(id: number): Promise<Preset> {
    return apiJson<Preset>(`/presets/${id}/default`, { method: "POST" });
}
