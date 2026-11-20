import type {
    AiEngine, AiImageSize, OutputFormat, ProcessingEngine, RembgModel, UpscaleMethod,
} from "../types/preset";

interface Option<T> {
    value: T;
    label: string;
}

/**
 * Validation ranges of `PresetConfig`, mirroring the server (out-of-range values are 422s).
 * Ranges the contract leaves open (thresholds, erode, upscale/AI/resize sizes) use the
 * previous backend limits.
 */
export const PRESET_LIMITS = {
    contrastFactor: { min: 0.5, max: 2.0, step: 0.05 },
    threshold: { min: 0, max: 255 },
    erodeSize: { min: 0, max: 100 },
    padding: { min: 0, max: 200 },
    upscaleBelow: { min: 1, max: 4000 },
    canvasSize: { min: 16, max: 8000 },
    fillRatio: { min: 0.1, max: 1.0, step: 0.05 },
    resizeSize: { min: 16, max: 8000 },
    quality: { min: 1, max: 95 },
    /** `max_bytes` lower bound (10 KiB); the editor works in KB. */
    minMaxBytes: 10240,
    /** `max_bytes` upper bound (100 MiB). */
    maxMaxBytes: 104857600,
    aiBelow: { min: 0, max: 8000 },
    promptLength: 4000,
    nameLength: 64,
    descriptionLength: 500,
} as const;

export const REMBG_MODEL_OPTIONS: Option<RembgModel>[] = [
    { value: "birefnet-general", label: "BiRefNet General (best quality)" },
    { value: "birefnet-general-lite", label: "BiRefNet Lite (faster)" },
    { value: "birefnet-massive", label: "BiRefNet Massive (slowest)" },
    { value: "isnet-general-use", label: "ISNet General" },
    { value: "u2net", label: "U²-Net" },
    { value: "u2netp", label: "U²-Net Lite" },
    { value: "silueta", label: "Silueta (small)" },
];

export const UPSCALE_METHOD_OPTIONS: Option<UpscaleMethod>[] = [
    { value: "esrgan", label: "Real-ESRGAN (AI, sharper)" },
    { value: "lanczos", label: "Lanczos (fast, classic)" },
];

export const OUTPUT_FORMAT_OPTIONS: Option<OutputFormat>[] = [
    { value: "keep", label: "Keep original format" },
    { value: "jpeg", label: "JPEG" },
    { value: "png", label: "PNG (lossless, transparency)" },
    { value: "webp", label: "WebP (transparency)" },
];

export const AI_ENGINE_LABELS: Record<Exclude<AiEngine, "none">, string> = {
    openai: "OpenAI",
    gemini: "Gemini",
};

export const AI_ENGINE_OPTIONS: Option<Exclude<AiEngine, "none">>[] = [
    { value: "openai", label: AI_ENGINE_LABELS.openai },
    { value: "gemini", label: AI_ENGINE_LABELS.gemini },
];

export const AI_SIZE_OPTIONS: Option<AiImageSize>[] = [
    { value: "auto", label: "Automatic" },
    { value: "1024x1024", label: "1024×1024 (square)" },
    { value: "1536x1024", label: "1536×1024 (landscape)" },
    { value: "1024x1536", label: "1024×1536 (portrait)" },
];

export const PROCESSING_ENGINE_OPTIONS: (Option<ProcessingEngine> & { description: string })[] = [
    { value: "preset", label: "As the preset says", description: "Use the preset's AI rule, local processing otherwise" },
    { value: "local", label: "Local only", description: "Never call an AI API" },
    { value: "openai", label: "OpenAI", description: "Regenerate every image with OpenAI (paid API)" },
    { value: "gemini", label: "Gemini", description: "Regenerate every image with Gemini (paid API)" },
];
