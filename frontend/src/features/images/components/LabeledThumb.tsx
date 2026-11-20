import { Image } from "antd";
import { CHECKERBOARD, IMAGE_FALLBACK } from "../../../utils/storageUrl";

interface LabeledThumbProps {
    label: string;
    url: string | null;
    size: number;
    /** Checkerboard behind the image, so transparency is visible. */
    checkerboard?: boolean;
}

/** Small captioned preview. */
export function LabeledThumb({ label, url, size, checkerboard }: LabeledThumbProps) {
    const background = checkerboard ? CHECKERBOARD : "#fff";
    return (
        <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 2 }}>{label}</div>
            {url ? (
                <Image
                    src={url} width={size} height={size} fallback={IMAGE_FALLBACK} alt={label}
                    loading="lazy" decoding="async"
                    style={{ objectFit: "contain", borderRadius: 6, border: "1px solid #e2e8f0", background }}
                />
            ) : (
                <div aria-label={`${label}: none`} role="img" style={{
                    width: size, height: size, background: "#f1f5f9", borderRadius: 6, border: "1px dashed #e2e8f0",
                }} />
            )}
        </div>
    );
}
