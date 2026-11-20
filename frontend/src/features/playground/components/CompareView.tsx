import { useId, useState } from "react";
import { Segmented, Typography } from "antd";
import { CHECKERBOARD } from "../../../utils/storageUrl";

const { Text } = Typography;

type CompareMode = "slider" | "side-by-side";

interface CompareViewProps {
    beforeUrl: string | null;
    afterUrl: string;
}

const FRAME = {
    position: "relative", height: 460, borderRadius: 10, overflow: "hidden",
    border: "1px solid #e2e8f0", background: CHECKERBOARD,
} as const;

const FILL = { position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" } as const;

function Caption({ side, children }: { side: "left" | "right"; children: string }) {
    return (
        <span style={{
            position: "absolute", top: 8, padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            background: "rgba(15, 23, 42, 0.7)", color: "#fff", pointerEvents: "none",
            [side]: 8,
        }}>
            {children}
        </span>
    );
}

function Slider({ beforeUrl, afterUrl }: { beforeUrl: string; afterUrl: string }) {
    const id = useId();
    const [position, setPosition] = useState(50);
    return (
        <div>
            <div style={FRAME}>
                <img src={afterUrl} alt="Result" style={FILL} />
                <img src={beforeUrl} alt="Original" referrerPolicy="no-referrer"
                     style={{ ...FILL, clipPath: `inset(0 ${100 - position}% 0 0)` }} />
                <div aria-hidden style={{
                    position: "absolute", top: 0, bottom: 0, left: `${position}%`, width: 2,
                    background: "#fff", boxShadow: "0 0 0 1px rgba(15,23,42,0.35)",
                }} />
                <Caption side="left">Before</Caption>
                <Caption side="right">After</Caption>
            </div>
            <label htmlFor={id} className="sr-only">Comparison position</label>
            <input id={id} type="range" min={0} max={100} value={position} onChange={event => setPosition(Number(event.target.value))}
                   aria-valuetext={`${position}% original`} style={{ width: "100%", marginTop: 8, accentColor: "#006A64" }} />
        </div>
    );
}

function Panel({ url, label }: { url: string | null; label: string }) {
    return (
        <figure style={{ margin: 0 }}>
            <div style={FRAME}>
                {url
                    ? <img src={url} alt={label} referrerPolicy="no-referrer" style={FILL} />
                    : <Text type="secondary" style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>No preview</Text>}
            </div>
            <figcaption style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{label}</figcaption>
        </figure>
    );
}

/** Before/after comparison: a draggable split, or two panels side by side. */
export function CompareView({ beforeUrl, afterUrl }: CompareViewProps) {
    const [mode, setMode] = useState<CompareMode>(beforeUrl ? "slider" : "side-by-side");
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Segmented<CompareMode>
                value={mode}
                onChange={setMode}
                options={[
                    { value: "slider", label: "Slider", disabled: !beforeUrl },
                    { value: "side-by-side", label: "Side by side" },
                ]}
                style={{ alignSelf: "flex-start" }}
            />
            {mode === "slider" && beforeUrl ? (
                <Slider beforeUrl={beforeUrl} afterUrl={afterUrl} />
            ) : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <Panel url={beforeUrl} label="Original" />
                    <Panel url={afterUrl} label="Result" />
                </div>
            )}
        </div>
    );
}
