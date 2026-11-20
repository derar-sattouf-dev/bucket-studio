import type { ReactNode } from "react";
import { Typography } from "antd";

const { Title, Text } = Typography;

interface PageHeaderProps {
    icon: ReactNode;
    iconColor: string;
    title: ReactNode;
    subtitle: ReactNode;
    /** Right-hand end colour of the banner gradient. */
    tint: string;
    /** Buttons or tags shown on the right. */
    extra?: ReactNode;
    marginBottom?: number;
}

/** The gradient banner at the top of every page. */
export function PageHeader({ icon, iconColor, title, subtitle, tint, extra, marginBottom = 24 }: PageHeaderProps) {
    return (
        <div style={{
            background: `linear-gradient(135deg, #ffffff 0%, ${tint} 100%)`,
            borderRadius: 14, border: "1px solid #e2e8f0",
            padding: "18px 24px", marginBottom,
            display: "flex", justifyContent: "space-between", alignItems: "center",
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}>
            <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 3 }}>
                    <span style={{ fontSize: 18, color: iconColor, display: "inline-flex" }}>{icon}</span>
                    <Title level={4} style={{ margin: 0, fontSize: 17, color: "#0f172a" }}>{title}</Title>
                </div>
                <Text style={{ fontSize: 12, color: "#64748b" }}>{subtitle}</Text>
            </div>
            {extra}
        </div>
    );
}
