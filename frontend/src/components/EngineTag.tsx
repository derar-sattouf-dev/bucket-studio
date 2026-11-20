import { Tag, Tooltip } from "antd";

const ENGINES: Record<string, { label: string; color: string }> = {
    local: { label: "Local", color: "cyan" },
    openai: { label: "OpenAI", color: "purple" },
    gemini: { label: "Gemini", color: "blue" },
};

/** Which engine produced the processed image (`processed_by` is "local" or "<engine>:<model>"). */
export function EngineTag({ processedBy }: { processedBy: string | null }) {
    if (!processedBy) return null;
    const [engine, model] = processedBy.split(":", 2);
    const meta = ENGINES[engine] ?? { label: engine, color: "default" };
    return (
        <Tooltip title={model ? `Model: ${model}` : undefined}>
            <Tag color={meta.color} style={{ fontSize: 11 }}>{meta.label}</Tag>
        </Tooltip>
    );
}
