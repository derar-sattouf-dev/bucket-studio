import type { CSSProperties, ReactNode } from "react";
import { Image } from "antd";
import type { ImageRecord } from "../../../types/image";
import { formatBytes, formatDateTime } from "../../../utils/format";
import { CHECKERBOARD, IMAGE_FALLBACK, toBrowserUrl } from "../../../utils/storageUrl";
import { dimensionsLabel } from "../imageUtils";

const PANEL_LABEL: CSSProperties = {
    fontSize: 11, fontWeight: 600, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em",
};

const IMAGE_BOX: CSSProperties = {
    border: "1px solid #e5e7eb", borderRadius: 8, minHeight: 320, overflow: "hidden",
    display: "flex", alignItems: "center", justifyContent: "center",
};

interface PanelProps {
    label: ReactNode;
    url: string | null;
    alt: string;
    empty: ReactNode;
    checkerboard?: boolean;
}

function Panel({ label, url, alt, empty, checkerboard }: PanelProps) {
    return (
        <div>
            <div style={PANEL_LABEL}>{label}</div>
            <div style={{ ...IMAGE_BOX, background: checkerboard ? CHECKERBOARD : "#f5f5f5" }}>
                {url
                    ? <Image src={url} alt={alt} style={{ maxHeight: 460, maxWidth: "100%", objectFit: "contain" }} fallback={IMAGE_FALLBACK} />
                    : empty}
            </div>
        </div>
    );
}

const muted = (text: string) => <span style={{ color: "#94a3b8", fontSize: 13 }}>{text}</span>;

/**
 * Side-by-side before/after. For published images the left panel is the backup of the
 * original and the right panel is the published file at the source key.
 */
export function DrawerComparison({ image }: { image: ImageRecord }) {
    const published = image.is_published;
    const dimensions = dimensionsLabel(image);
    const originalLabel = published
        ? "Original (backup)"
        : ["Original", dimensions, formatBytes(image.source_size)].filter(Boolean).join(" · ");
    const resultLabel = `${published ? "Published" : "Result"} · ${formatBytes(image.processed_size)}` +
        (image.processed_at ? ` · ${formatDateTime(image.processed_at)}` : "");

    const notProcessed = (
        <div style={{ textAlign: "center", padding: "0 12px" }}>
            {muted(image.status === "failed" ? "Processing failed" : "Not processed yet")}
            {image.status === "failed" && image.error_message && (
                <span style={{ color: "#cf1322", fontSize: 11, display: "block", marginTop: 4 }}>{image.error_message}</span>
            )}
        </div>
    );

    return (
        <Image.PreviewGroup>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
                <Panel
                    label={originalLabel}
                    alt="Original"
                    url={toBrowserUrl(published ? image.backup_url : image.source_url)}
                    empty={muted(published ? "Backup not found" : "No image")}
                />
                <Panel
                    label={resultLabel}
                    alt="Processed result"
                    checkerboard
                    url={toBrowserUrl(published ? image.source_url : image.processed_url)}
                    empty={notProcessed}
                />
            </div>
        </Image.PreviewGroup>
    );
}
