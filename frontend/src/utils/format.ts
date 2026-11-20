/** Human-readable byte size; "—" for missing or zero values. */
export function formatBytes(bytes: number | null | undefined): string {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/** "42s" / "3m 5s"; "—" when unknown. */
export function formatDuration(seconds: number | null | undefined): string {
    if (seconds == null) return "—";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

export function formatDateTime(iso: string | null | undefined): string {
    return iso ? new Date(iso).toLocaleString() : "—";
}

/** Relative time such as "5m ago"; `now` is injectable so render stays pure. */
export function formatTimeAgo(iso: string, now: number): string {
    const minutes = Math.floor((now - new Date(iso).getTime()) / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
    return count === 1 ? singular : plural;
}

/** Splits an S3 key into its folder and file name. */
export function splitKey(key: string): { folder: string; file: string } {
    const parts = key.split("/");
    const file = parts.pop() ?? key;
    return { folder: parts.join("/"), file };
}

const UNITS: [seconds: number, label: string][] = [[86400, "d"], [3600, "h"], [60, "min"], [1, "s"]];

/** Readable length of a period, e.g. 43200 → "12 h", 5400 → "1 h 30 min" (two largest units). */
export function humanizeSeconds(total: number | null | undefined): string {
    if (total == null || !Number.isFinite(total)) return "—";
    if (total <= 0) return "0 s";
    const parts: string[] = [];
    let rest = Math.round(total);
    for (const [size, label] of UNITS) {
        if (rest >= size && parts.length < 2) {
            parts.push(`${Math.floor(rest / size)} ${label}`);
            rest %= size;
        }
    }
    return parts.join(" ");
}

export const humanizeMinutes = (minutes: number | null | undefined) =>
    humanizeSeconds(minutes == null ? minutes : minutes * 60);
