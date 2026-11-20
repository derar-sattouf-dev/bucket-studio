import { Select, Typography } from "antd";
import { PROCESSING_ENGINE_OPTIONS } from "../constants/presetOptions";
import type { ProcessingEngine } from "../types/preset";

const { Text } = Typography;

interface EngineSelectProps {
    id?: string;
    value: ProcessingEngine;
    onChange: (engine: ProcessingEngine) => void;
    disabled?: boolean;
}

/** Engine override for a processing run. */
export function EngineSelect({ id, value, onChange, disabled }: EngineSelectProps) {
    return (
        <Select<ProcessingEngine>
            id={id}
            value={value}
            onChange={onChange}
            disabled={disabled}
            style={{ width: "100%" }}
            optionLabelProp="title"
            options={PROCESSING_ENGINE_OPTIONS.map(({ value: engine, label, description }) => ({
                value: engine,
                title: label,
                label: (
                    <div>
                        <div>{label}</div>
                        <Text type="secondary" style={{ fontSize: 11 }}>{description}</Text>
                    </div>
                ),
            }))}
        />
    );
}
