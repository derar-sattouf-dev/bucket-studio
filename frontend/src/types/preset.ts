/** Shapes of `PresetConfig` and `PresetOut` from the API. Every config field has a server default. */

export type RembgModel =
    | "birefnet-general"
    | "birefnet-general-lite"
    | "birefnet-massive"
    | "isnet-general-use"
    | "u2net"
    | "u2netp"
    | "silueta";

export type UpscaleMethod = "esrgan" | "lanczos";
export type OutputFormat = "keep" | "jpeg" | "png" | "webp";
export type AiEngine = "none" | "openai" | "gemini";
export type AiImageSize = "auto" | "1024x1024" | "1536x1024" | "1024x1536";

/** Canvas background: `#RRGGBB` or the literal `"transparent"`. */
export type CanvasBackground = string;

export interface ContrastConfig {
    enabled: boolean;
    factor: number;
}

export interface BackgroundConfig {
    remove: boolean;
    model: RembgModel;
    skip_if_plain: boolean;
    plain_threshold: number;
    alpha_matting: boolean;
    fg_threshold: number;
    bg_threshold: number;
    erode_size: number;
}

export interface AutocropConfig {
    enabled: boolean;
    padding: number;
}

export interface UpscaleConfig {
    enabled: boolean;
    below_px: number;
    method: UpscaleMethod;
}

export interface CanvasConfig {
    enabled: boolean;
    width: number;
    height: number;
    fill_ratio: number;
    background: CanvasBackground;
}

export interface ResizeConfig {
    max_width: number | null;
    max_height: number | null;
}

export interface OutputConfig {
    format: OutputFormat;
    quality: number;
    max_bytes: number | null;
}

export interface AiConfig {
    engine: AiEngine;
    below_px: number;
    prompt: string | null;
    size: AiImageSize;
}

export interface PresetConfig {
    contrast: ContrastConfig;
    background: BackgroundConfig;
    autocrop: AutocropConfig;
    upscale: UpscaleConfig;
    canvas: CanvasConfig;
    resize: ResizeConfig;
    output: OutputConfig;
    ai: AiConfig;
}

export interface Preset {
    id: number;
    name: string;
    description: string;
    config: PresetConfig;
    is_default: boolean;
    created_at: string;
    updated_at: string;
}

export interface PresetDraft {
    name: string;
    description: string;
    config: PresetConfig;
}

/**
 * Engine override for a processing run: "preset" follows the preset's AI rule, "local"
 * forces local processing, "openai"/"gemini" force that model.
 */
export type ProcessingEngine = "preset" | "local" | "openai" | "gemini";
