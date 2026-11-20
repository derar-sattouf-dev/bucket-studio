import type { CSSProperties, ReactNode } from "react";

/** Standard page padding. */
export function PageContainer({ children, style }: { children: ReactNode; style?: CSSProperties }) {
    return <div style={{ padding: "28px 36px", ...style }}>{children}</div>;
}
