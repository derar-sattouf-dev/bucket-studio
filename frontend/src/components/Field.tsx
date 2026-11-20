import type { ReactNode } from "react";
import { Typography } from "antd";

const { Text } = Typography;

interface FieldProps {
    /** id of the control, so the label is announced with it. */
    htmlFor: string;
    label: ReactNode;
    help?: ReactNode;
    children: ReactNode;
}

/** Label + control + help text, used by every preset section. */
export function Field({ htmlFor, label, help, children }: FieldProps) {
    return (
        <div>
            <label htmlFor={htmlFor} style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#334155", marginBottom: 4 }}>
                {label}
            </label>
            {children}
            {help && <Text type="secondary" style={{ display: "block", fontSize: 11, marginTop: 3 }}>{help}</Text>}
        </div>
    );
}

/** Responsive grid of fields. */
export function FieldGrid({ children }: { children: ReactNode }) {
    return (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "14px 16px" }}>
            {children}
        </div>
    );
}

interface InlineSwitchFieldProps {
    label: ReactNode;
    help?: ReactNode;
    /** The switch, labelled via `aria-label`. */
    control: ReactNode;
}

/** A boolean option inside a section: text on the left, switch on the right. */
export function InlineSwitchField({ label, help, control }: InlineSwitchFieldProps) {
    return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div>
                <Text strong style={{ fontSize: 12 }}>{label}</Text>
                {help && <Text type="secondary" style={{ display: "block", fontSize: 11 }}>{help}</Text>}
            </div>
            {control}
        </div>
    );
}
