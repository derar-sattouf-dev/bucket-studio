import type { PlaygroundRecipe, PlaygroundResult } from "../types/playground";
import { apiFetch } from "./client";

function filenameFromDisposition(header: string | null): string | null {
    const match = header?.match(/filename="(.+?)"/);
    return match ? match[1] : null;
}

function parseProcessingMs(header: string | null): number | null {
    const value = header === null ? NaN : Number(header);
    return Number.isFinite(value) ? value : null;
}

async function toResult(response: Response, fallbackName: string): Promise<PlaygroundResult> {
    return {
        blob: await response.blob(),
        filename: filenameFromDisposition(response.headers.get("Content-Disposition")) ?? fallbackName,
        processingMs: parseProcessingMs(response.headers.get("X-Processing-Ms")),
    };
}

/** Processes an upload in memory with a preset or an unsaved config; nothing is stored. */
export async function runPlaygroundUpload(file: File, recipe: PlaygroundRecipe, signal?: AbortSignal): Promise<PlaygroundResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("engine", recipe.engine);
    if (recipe.kind === "preset") form.append("preset_id", String(recipe.presetId));
    else form.append("config", JSON.stringify(recipe.config));
    const response = await apiFetch("/playground/", { method: "POST", body: form, signal });
    return toResult(response, `processed_${file.name}`);
}

/** Same as {@link runPlaygroundUpload}, but the server fetches the image from a public URL. */
export async function runPlaygroundUrl(url: string, recipe: PlaygroundRecipe, signal?: AbortSignal): Promise<PlaygroundResult> {
    const json = recipe.kind === "preset"
        ? { url, engine: recipe.engine, preset_id: recipe.presetId }
        : { url, engine: recipe.engine, config: recipe.config };
    const response = await apiFetch("/playground/from-url", { method: "POST", json, signal });
    return toResult(response, "processed_image");
}
