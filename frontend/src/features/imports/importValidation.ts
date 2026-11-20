/** Limits of `POST /imports`, mirrored so problems are reported before submitting. */
export const IMPORT_LIMITS = { maxUrls: 100, maxUrlLength: 2048, maxFolderLength: 256 } as const;

const FOLDER_PATTERN = /^([A-Za-z0-9._-]+\/)*$/;

/** One URL per line; blank lines and duplicates are dropped. */
export function parseUrlList(text: string): string[] {
    return [...new Set(text.split(/\r?\n/).map(line => line.trim()).filter(Boolean))];
}

function isHttpUrl(value: string): boolean {
    try {
        const { protocol } = new URL(value);
        return protocol === "http:" || protocol === "https:";
    } catch {
        return false;
    }
}

/** Returns a user-facing error, or null when the list can be submitted. */
export function validateUrls(urls: string[]): string | null {
    if (urls.length === 0) return "Paste at least one image URL.";
    if (urls.length > IMPORT_LIMITS.maxUrls) return `At most ${IMPORT_LIMITS.maxUrls} URLs per import (you have ${urls.length}).`;
    const tooLong = urls.find(url => url.length > IMPORT_LIMITS.maxUrlLength);
    if (tooLong) return `URLs are limited to ${IMPORT_LIMITS.maxUrlLength} characters.`;
    const invalid = urls.find(url => !isHttpUrl(url));
    return invalid ? `Not an http(s) URL: ${invalid}` : null;
}

/** Trims, drops leading slashes and adds the trailing "/" the API expects ("" = prefix root). */
export function normaliseFolder(value: string): string {
    const trimmed = value.trim().replace(/^\/+/, "");
    return trimmed && !trimmed.endsWith("/") ? `${trimmed}/` : trimmed;
}

export function validateFolder(folder: string): string | null {
    if (folder.length > IMPORT_LIMITS.maxFolderLength) return `Folder is limited to ${IMPORT_LIMITS.maxFolderLength} characters.`;
    if (!FOLDER_PATTERN.test(folder) || folder.split("/").some(part => part === "." || part === "..")) {
        return 'Use folder names made of letters, digits, ".", "_" and "-", separated by "/".';
    }
    return null;
}
