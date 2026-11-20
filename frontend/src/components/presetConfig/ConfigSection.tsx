import { useId, type ReactNode } from "react";
import { Alert, Switch, Typography } from "antd";

const { Text } = Typography;

interface ConfigSectionProps {
    title: string;
    description: ReactNode;
    /** Omit for sections that always apply (no switch). */
    enabled?: boolean;
    onToggle?: (enabled: boolean) => void;
    disabled?: boolean;
    /** Validation messages for this section. */
    issues?: string[];
    /** Shown above the fields, e.g. "ignored while the canvas is on". */
    note?: ReactNode;
    children: ReactNode;
}

/** One pipeline step in the preset editor; its fields only show while it is enabled. */
export function ConfigSection(props: ConfigSectionProps) {
    const { title, description, enabled = true, onToggle, disabled, issues = [], note, children } = props;
    const titleId = useId();
    const hasSwitch = onToggle !== undefined;

    return (
        <section
            aria-labelledby={titleId}
            style={{
                border: `1px solid ${issues.length ? "#ffccc7" : "#e2e8f0"}`,
                borderRadius: 10,
                background: enabled ? "#fff" : "#f8fafc",
                padding: "12px 16px",
            }}
        >
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div>
                    <Text id={titleId} strong style={{ fontSize: 14 }}>{title}</Text>
                    <Text type="secondary" style={{ display: "block", fontSize: 12 }}>{description}</Text>
                </div>
                {hasSwitch && (
                    <Switch checked={enabled} onChange={onToggle} disabled={disabled} aria-label={`Enable ${title.toLowerCase()}`} />
                )}
            </div>
            {enabled && (
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                    {note}
                    {children}
                </div>
            )}
            {issues.map(issue => <Alert key={issue} type="error" showIcon title={issue} style={{ marginTop: 10 }} />)}
        </section>
    );
}
