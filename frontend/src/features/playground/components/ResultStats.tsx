import { Descriptions } from "antd";
import { formatBytes } from "../../../utils/format";
import type { Dimensions } from "../hooks/useImageDimensions";

interface ResultStatsProps {
    originalBytes: number | null;
    originalDimensions: Dimensions | null;
    resultBytes: number;
    resultDimensions: Dimensions | null;
    resultType: string;
    processingMs: number | null;
}

const dims = (value: Dimensions | null) => (value ? `${value.width}×${value.height}` : "—");

function sizeChange(before: number | null, after: number): string | null {
    if (!before) return null;
    const percent = Math.round(((after - before) / before) * 100);
    return `${percent > 0 ? "+" : ""}${percent}%`;
}

function formatMs(ms: number | null): string {
    if (ms === null) return "—";
    return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Sizes, dimensions and server time of a playground run. */
export function ResultStats(props: ResultStatsProps) {
    const { originalBytes, originalDimensions, resultBytes, resultDimensions, resultType, processingMs } = props;
    const change = sizeChange(originalBytes, resultBytes);
    return (
        <Descriptions
            size="small" bordered
            column={{ xs: 1, sm: 2, md: 2, lg: 2, xl: 2, xxl: 2 }}
            styles={{ label: { whiteSpace: "nowrap" }, content: { whiteSpace: "nowrap" } }}
        >
            <Descriptions.Item label="Original">{dims(originalDimensions)} · {formatBytes(originalBytes)}</Descriptions.Item>
            <Descriptions.Item label="Result">
                {dims(resultDimensions)} · {formatBytes(resultBytes)}{change && ` (${change})`}
            </Descriptions.Item>
            <Descriptions.Item label="Format">{resultType || "—"}</Descriptions.Item>
            <Descriptions.Item label="Processing time">{formatMs(processingMs)}</Descriptions.Item>
        </Descriptions>
    );
}
