import { Select, Tag } from "antd";
import type { Preset } from "../types/preset";

interface PresetSelectProps {
    id?: string;
    presets: Preset[];
    value: number | null;
    onChange: (presetId: number) => void;
    loading?: boolean;
    disabled?: boolean;
}

/** Preset dropdown; the default preset is tagged. */
export function PresetSelect({ id, presets, value, onChange, loading, disabled }: PresetSelectProps) {
    return (
        <Select<number>
            id={id}
            value={value ?? undefined}
            onChange={onChange}
            loading={loading}
            disabled={disabled}
            placeholder="Choose a preset"
            style={{ width: "100%" }}
            showSearch={{ optionFilterProp: "title" }}
            options={presets.map(preset => ({
                value: preset.id,
                title: preset.name,
                label: (
                    <span>
                        {preset.name}
                        {preset.is_default && <Tag color="green" style={{ marginInlineStart: 8, fontSize: 11 }}>default</Tag>}
                    </span>
                ),
            }))}
        />
    );
}
