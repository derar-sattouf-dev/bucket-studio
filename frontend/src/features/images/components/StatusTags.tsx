import type { CSSProperties } from "react";
import { Tag } from "antd";
import type { DisplayStatus } from "../../../types/image";
import { STATUS_TAG } from "../constants";

export function StatusTag({ status, style }: { status: DisplayStatus; style?: CSSProperties }) {
    const { color, icon, label } = STATUS_TAG[status];
    return <Tag icon={icon} color={color} style={style}>{label}</Tag>;
}
