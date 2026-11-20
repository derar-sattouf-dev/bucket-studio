import { AI_ENGINE_LABELS, PRESET_LIMITS } from "../constants/presetOptions";
import type { OutputFormat, PresetConfig, ProcessingEngine } from "../types/preset";

export const TRANSPARENT = "transparent";

const HEX_COLOR = /^#[0-9A-Fa-f]{6}$/;

/**
 * Server defaults for every field; partial configs are completed from these. Every step is off:
 * a new preset changes nothing until a step is switched on. The numbers are starting values.
 */
export const DEFAULT_PRESET_CONFIG: PresetConfig = {
    contrast: { enabled: false, factor: 1.1 },
    background: {
        remove: false, model: "birefnet-general", skip_if_plain: false, plain_threshold: 230,
        alpha_matting: false, fg_threshold: 240, bg_threshold: 10, erode_size: 10,
    },
    autocrop: { enabled: false, padding: 4 },
    upscale: { enabled: false, below_px: 800, method: "esrgan" },
    canvas: { enabled: false, width: 1000, height: 1000, fill_ratio: 0.85, background: "#FFFFFF" },
    resize: { max_width: null, max_height: null },
    output: { format: "keep", quality: 90, max_bytes: null },
    ai: { engine: "none", below_px: 0, prompt: null, size: "auto" },
};

export type PartialPresetConfig = { [Section in keyof PresetConfig]?: Partial<PresetConfig[Section]> };

/** Fills every missing field from {@link DEFAULT_PRESET_CONFIG}. */
export function withDefaults(config: PartialPresetConfig): PresetConfig {
    const d = DEFAULT_PRESET_CONFIG;
    return {
        contrast: { ...d.contrast, ...config.contrast },
        background: { ...d.background, ...config.background },
        autocrop: { ...d.autocrop, ...config.autocrop },
        upscale: { ...d.upscale, ...config.upscale },
        canvas: { ...d.canvas, ...config.canvas },
        resize: { ...d.resize, ...config.resize },
        output: { ...d.output, ...config.output },
        ai: { ...d.ai, ...config.ai },
    };
}

/**
 * Whether the result keeps an alpha channel: a transparent canvas, or background removal
 * without a canvas to flatten it onto.
 */
export function producesTransparency(config: PresetConfig): boolean {
    return config.canvas.enabled ? config.canvas.background === TRANSPARENT : config.background.remove;
}

const TRANSPARENT_FORMATS: readonly OutputFormat[] = ["png", "webp", "keep"];

export interface ConfigIssue {
    section: keyof PresetConfig;
    message: string;
}

/** Cross-field rules the inputs cannot enforce on their own. Empty array = valid. */
export function validatePresetConfig(config: PresetConfig): ConfigIssue[] {
    const issues: ConfigIssue[] = [];
    const { canvas, output, ai } = config;

    if (canvas.enabled && canvas.background !== TRANSPARENT && !HEX_COLOR.test(canvas.background)) {
        issues.push({ section: "canvas", message: "Background must be a #RRGGBB color or transparent." });
    }
    if (producesTransparency(config) && !TRANSPARENT_FORMATS.includes(output.format)) {
        issues.push({ section: "output", message: "Transparent output needs PNG or WebP (JPEG has no alpha channel)." });
    }
    if (output.max_bytes !== null && output.max_bytes < PRESET_LIMITS.minMaxBytes) {
        issues.push({ section: "output", message: "The file size limit must be at least 10 KB." });
    }
    if ((ai.prompt ?? "").length > PRESET_LIMITS.promptLength) {
        issues.push({ section: "ai", message: `The prompt is limited to ${PRESET_LIMITS.promptLength} characters.` });
    }
    return issues;
}

export function isResizeEnabled({ resize }: PresetConfig): boolean {
    return resize.max_width !== null || resize.max_height !== null;
}

function describeBackground(color: string): string {
    if (color === TRANSPARENT) return "transparent";
    if (color.toUpperCase() === "#FFFFFF") return "white";
    return color.toUpperCase();
}

function describeOutput({ format, quality, max_bytes }: PresetConfig["output"]): string {
    const base = format === "keep" ? "Keep format" : format.toUpperCase();
    const lossy = format === "jpeg" || format === "webp" || format === "keep";
    const withQuality = lossy ? `${base} · q${quality}` : base;
    return max_bytes ? `${withQuality} · ≤ ${Math.round(max_bytes / 1024)} KB` : withQuality;
}

/** Short, human-readable steps of a preset, in pipeline order. */
export function describePresetSteps(config: PresetConfig): string[] {
    const { contrast, background, autocrop, upscale, canvas, resize, ai } = config;
    const steps: string[] = [];
    if (ai.engine !== "none") {
        const when = ai.below_px > 0 ? `below ${ai.below_px} px` : "always";
        steps.push(`AI: ${AI_ENGINE_LABELS[ai.engine]} (${when})`);
    }
    if (contrast.enabled) steps.push(`Contrast ×${contrast.factor}`);
    if (background.remove) steps.push("Remove background");
    if (autocrop.enabled) steps.push(`Autocrop ${autocrop.padding} px`);
    if (upscale.enabled) steps.push(`Upscale below ${upscale.below_px} px`);
    if (canvas.enabled) steps.push(`Canvas ${canvas.width}×${canvas.height} ${describeBackground(canvas.background)}`);
    else if (isResizeEnabled(config)) steps.push(`Fit within ${resize.max_width ?? "∞"}×${resize.max_height ?? "∞"}`);
    steps.push(describeOutput(config.output));
    return steps;
}

/** Engines that send the image to a third-party API. */
export const isAiEngine = (engine: ProcessingEngine) => engine === "openai" || engine === "gemini";
