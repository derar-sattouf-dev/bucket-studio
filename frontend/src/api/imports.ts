import type { ImportRequest, ImportResult } from "../types/import";
import { apiJson } from "./client";

/** Downloads each URL server-side into the source prefix and registers it as pending. */
export function importFromUrls(request: ImportRequest): Promise<ImportResult> {
    return apiJson<ImportResult>("/imports/", { method: "POST", json: request });
}
