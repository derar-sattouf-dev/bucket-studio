/**
 * Presigned URLs generated inside docker-compose point at the internal `minio` host,
 * which the browser cannot resolve; rewrite them to the published port for local dev.
 */
export function toBrowserUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    return url.replace(/http:\/\/minio:\d+/, "http://localhost:9000");
}

/** 1×1 transparent PNG shown by antd <Image> when a preview fails to load. */
export const IMAGE_FALLBACK =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg==";

/** Checkerboard backdrop that makes transparent pixels visible. */
export const CHECKERBOARD = "repeating-conic-gradient(#e2e8f0 0% 25%, #ffffff 0% 50%) 50% / 12px 12px";
