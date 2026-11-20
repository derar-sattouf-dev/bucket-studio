import type { CSSProperties } from "react";

const KEY_STYLE: CSSProperties = {
    background: "#f1f5f9", border: "1px solid #e2e8f0", padding: "1px 6px",
    borderRadius: 4, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
};

const SHORTCUTS = [
    { key: "A", label: "select all" },
    { key: "P", label: "process selection" },
    { key: "Esc", label: "deselect" },
];

export function KeyboardHint() {
    return (
        <p style={{ marginBottom: 10, fontSize: 11, color: "#94a3b8" }}>
            {SHORTCUTS.map(({ key, label }, index) => (
                <span key={key}>
                    <kbd style={{ ...KEY_STYLE, margin: index === 0 ? "0 4px 0 0" : "0 4px 0 12px" }}>{key}</kbd> {label}
                </span>
            ))}
        </p>
    );
}
