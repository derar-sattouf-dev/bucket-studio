import type { ReactNode } from "react";
import { Typography } from "antd";

/** Help text under a settings field. */
export function FieldDesc({ children }: { children: ReactNode }) {
    return <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 2 }}>{children}</Typography.Text>;
}
