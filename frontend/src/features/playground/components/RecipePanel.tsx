import { useId } from "react";
import { Alert, Space, Switch, Tag, Typography } from "antd";
import { EngineSelect } from "../../../components/EngineSelect";
import { PresetSelect } from "../../../components/PresetSelect";
import { PresetConfigEditor } from "../../../components/presetConfig/PresetConfigEditor";
import type { Preset, PresetConfig, ProcessingEngine } from "../../../types/preset";
import { describePresetSteps, isAiEngine } from "../../../utils/presetConfig";

const { Text } = Typography;

interface RecipePanelProps {
    presets: Preset[];
    presetsLoading: boolean;
    presetId: number | null;
    onPresetChange: (presetId: number) => void;
    /** Unsaved tweaks of the selected preset; `null` runs the preset as saved. */
    customConfig: PresetConfig | null;
    onCustomize: (on: boolean) => void;
    onConfigChange: (config: PresetConfig) => void;
    engine: ProcessingEngine;
    onEngineChange: (engine: ProcessingEngine) => void;
}

/** Preset + optional inline tweaks + engine. Tweaks are never saved. */
export function RecipePanel(props: RecipePanelProps) {
    const { presets, presetsLoading, presetId, onPresetChange, customConfig, onCustomize, onConfigChange, engine, onEngineChange } = props;
    const id = useId();
    const preset = presets.find(candidate => candidate.id === presetId);
    const shownConfig = customConfig ?? preset?.config;

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
                <label htmlFor={`${id}-preset`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Preset</label>
                <PresetSelect id={`${id}-preset`} presets={presets} value={presetId} onChange={onPresetChange} loading={presetsLoading} />
                {shownConfig && (
                    <Space size={[4, 4]} wrap style={{ marginTop: 8 }}>
                        {describePresetSteps(shownConfig).map(step => <Tag key={step} style={{ fontSize: 11 }}>{step}</Tag>)}
                    </Space>
                )}
            </div>
            <div>
                <label htmlFor={`${id}-engine`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Engine</label>
                <EngineSelect id={`${id}-engine`} value={engine} onChange={onEngineChange} />
                {isAiEngine(engine) && (
                    <Alert type="warning" showIcon style={{ marginTop: 8 }} title="The image is sent to a paid third-party API." />
                )}
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <div>
                    <Text strong>Tweak settings</Text>
                    <Text type="secondary" style={{ display: "block", fontSize: 12 }}>Edit a copy of the preset for this test only.</Text>
                </div>
                <Switch checked={customConfig !== null} onChange={onCustomize} disabled={!preset && customConfig === null}
                        aria-label="Tweak preset settings" />
            </div>
            {customConfig && <PresetConfigEditor value={customConfig} onChange={onConfigChange} />}
        </div>
    );
}
