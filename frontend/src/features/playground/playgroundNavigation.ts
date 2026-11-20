import type { PresetConfig } from "../../types/preset";
import { withDefaults, type PartialPresetConfig } from "../../utils/presetConfig";

/** Router state carrying an unsaved config into the Playground (e.g. from the preset editor). */
interface PlaygroundLocationState {
    config: PresetConfig;
}

export const playgroundLink = (presetId: number) => `/playground?preset=${presetId}`;

export const playgroundState = (config: PresetConfig): PlaygroundLocationState => ({ config });

/** Reads the config from `location.state`, which is untyped (it survives reloads via history). */
export function readPlaygroundState(state: unknown): PresetConfig | null {
    if (!state || typeof state !== "object" || !("config" in state)) return null;
    const { config } = state as { config: unknown };
    return config && typeof config === "object" ? withDefaults(config as PartialPresetConfig) : null;
}
