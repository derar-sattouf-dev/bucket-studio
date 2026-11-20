import type { PresetConfig, ProcessingEngine } from "./preset";

/** Either a saved preset or an unsaved config; never both. */
export type PlaygroundRecipe =
    | { kind: "preset"; presetId: number; engine: ProcessingEngine }
    | { kind: "config"; config: PresetConfig; engine: ProcessingEngine };

export interface PlaygroundResult {
    blob: Blob;
    filename: string;
    /** Server-side processing time from `X-Processing-Ms`, when exposed. */
    processingMs: number | null;
}
