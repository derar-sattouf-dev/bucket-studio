export interface ImportRequest {
    urls: string[];
    /** Relative folder under the source prefix: empty or `a/b/` (trailing slash). */
    folder: string;
}

export interface ImportedImage {
    url: string;
    key: string;
    size: number;
}

export interface FailedImport {
    url: string;
    error: string;
}

export interface ImportResult {
    imported: ImportedImage[];
    failed: FailedImport[];
}
