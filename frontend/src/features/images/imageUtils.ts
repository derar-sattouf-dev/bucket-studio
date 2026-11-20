import type { DisplayStatus, GroupImagesPage, ImagePage, ImageRecord, TaskStatus } from "../../types/image";

export function isBusy(image: ImageRecord): boolean {
    return image.is_processing || image.status === "processing";
}

export const isPublishable = (image: ImageRecord) => image.status === "processed" && !image.is_published;

export const isResettable = (image: ImageRecord) =>
    (image.status === "processed" || image.status === "failed") && !image.is_published;

export function displayStatus(image: ImageRecord): DisplayStatus {
    if (isBusy(image)) return "processing";
    return image.is_published ? "published" : image.status;
}

/** Summarises a group: any busy → processing, then failed, pending, all published → published. */
export function groupStatus(images: ImageRecord[]): DisplayStatus {
    if (images.some(isBusy)) return "processing";
    if (images.some(image => image.status === "failed")) return "failed";
    if (images.some(image => image.status === "pending")) return "pending";
    if (images.length > 0 && images.every(image => image.is_published)) return "published";
    return "processed";
}

export function mapImages(page: ImagePage, update: (image: ImageRecord) => ImageRecord): ImagePage {
    return {
        ...page,
        items: page.items.map(group => ({ ...group, images: group.images.map(update) })),
    };
}

/** Adds a further slice of one group's images to the page (skipping images that are already there). */
export function appendToGroup(page: ImagePage, more: GroupImagesPage): ImagePage {
    return {
        ...page,
        items: page.items.map(group => {
            if (group.group !== more.group) return group;
            const known = new Set(group.images.map(image => image.source_key));
            const added = more.items.filter(image => !known.has(image.source_key));
            return { ...group, images: [...group.images, ...added], image_count: more.total };
        }),
    };
}

/** Optimistic update from a stream event; a final reload fetches authoritative data. */
export function applyTaskStatus(image: ImageRecord, status: TaskStatus | undefined): ImageRecord {
    if (!status) return image;
    const next: ImageRecord = { ...image, is_processing: status === "processing" };
    if (status === "done") next.status = "processed";
    if (status === "failed" || status === "aborted") next.status = "failed";
    return next;
}

export function fileName(key: string): string {
    return key.split("/").pop() ?? key;
}

/** "1200×800" or "" when unknown. */
export function dimensionsLabel(image: ImageRecord): string {
    return image.source_width && image.source_height ? `${image.source_width}×${image.source_height}` : "";
}

export const keysOf = (images: ImageRecord[]) => images.map(image => image.source_key);

/** Tags are stored as one comma-separated string. */
export function parseTags(tags: string | null): string[] {
    return (tags ?? "").split(",").map(tag => tag.trim()).filter(Boolean);
}
