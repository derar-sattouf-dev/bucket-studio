import type { BucketPrefixes } from "../../types/settings";

export const PREFIX_LABELS: Record<keyof BucketPrefixes, string> = {
    source_prefix: "Source prefix",
    output_prefix: "Output prefix",
    backup_prefix: "Backup prefix",
};

// Same rule as the backend: S3-safe characters, no leading slash, trailing slash required.
const PREFIX_PATTERN = /^[A-Za-z0-9!_.*'()-][A-Za-z0-9!_.*'()/-]*\/$/;

/** Trims whitespace and appends the trailing "/" users often forget. */
export function normalisePrefix(value: string): string {
    const trimmed = value.trim();
    return trimmed && !trimmed.endsWith("/") ? `${trimmed}/` : trimmed;
}

/** Returns a user-facing error, or null when the three prefixes are valid together. */
export function validatePrefixes(prefixes: BucketPrefixes): string | null {
    const entries = Object.entries(prefixes) as [keyof BucketPrefixes, string][];
    for (const [key, value] of entries) {
        const label = PREFIX_LABELS[key];
        if (!value) return `${label} cannot be empty`;
        if (value.startsWith("/")) return `${label} must not start with "/"`;
        if (!PREFIX_PATTERN.test(value)) {
            return `${label} may only contain letters, digits, "/" and !_.*'()- and must end with "/"`;
        }
    }
    const values = entries.map(([, value]) => value);
    if (new Set(values).size !== values.length) return "Source, output and backup prefixes must all be different";
    for (const [keyA, a] of entries) {
        for (const [keyB, b] of entries) {
            if (keyA !== keyB && a.startsWith(b)) {
                return `${PREFIX_LABELS[keyA]} must not be inside ${PREFIX_LABELS[keyB].toLowerCase()}`;
            }
        }
    }
    return null;
}
