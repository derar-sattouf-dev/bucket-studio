import { useId, useState } from "react";
import { Alert, Input, Modal, Space, Tag, Typography } from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { EngineSelect } from "../../../components/EngineSelect";
import { PresetSelect } from "../../../components/PresetSelect";
import { PRESET_LIMITS } from "../../../constants/presetOptions";
import type { ProcessOptions } from "../../../types/image";
import type { Preset, ProcessingEngine } from "../../../types/preset";
import { pluralize } from "../../../utils/format";
import { describePresetSteps, isAiEngine } from "../../../utils/presetConfig";

const { Text } = Typography;

interface ProcessDialogProps {
    /** How many images the run covers. */
    imageCount: number;
    presets: Preset[];
    presetsLoading: boolean;
    loading: boolean;
    onClose: () => void;
    onSubmit: (options: ProcessOptions) => void;
}

/** Choose a preset (default preselected) and an engine, then queue the images. Mount it to open it. */
export function ProcessDialog({ imageCount, presets, presetsLoading, loading, onClose, onSubmit }: ProcessDialogProps) {
    const id = useId();
    const [chosenPresetId, setPresetId] = useState<number | null>(null);
    const [engine, setEngine] = useState<ProcessingEngine>("preset");
    const [prompt, setPrompt] = useState("");

    // Until the user picks one, follow the default preset (the list may still be loading).
    const presetId = chosenPresetId ?? presets.find(preset => preset.is_default)?.id ?? null;
    const preset = presets.find(candidate => candidate.id === presetId);
    const usesAi = isAiEngine(engine) || (engine === "preset" && preset?.config.ai.engine !== "none");
    const count = `${imageCount.toLocaleString()} ${pluralize(imageCount, "image")}`;

    return (
        <Modal
            open
            title={<Space><ThunderboltOutlined />Process {count}</Space>}
            okText={`Process ${count}`}
            okButtonProps={{ disabled: presetId === null }}
            confirmLoading={loading}
            onCancel={onClose}
            onOk={() => presetId !== null && onSubmit({ presetId, engine, prompt: usesAi ? prompt.trim() : undefined })}
            width={560}
        >
            <Space orientation="vertical" size={14} style={{ width: "100%", marginTop: 8 }}>
                <div>
                    <label htmlFor={`${id}-preset`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Preset</label>
                    <PresetSelect id={`${id}-preset`} presets={presets} value={presetId} onChange={setPresetId} loading={presetsLoading} />
                    {preset && (
                        <Space size={[4, 4]} wrap style={{ marginTop: 8 }}>
                            {describePresetSteps(preset.config).map(step => <Tag key={step} style={{ fontSize: 11 }}>{step}</Tag>)}
                        </Space>
                    )}
                </div>
                <div>
                    <label htmlFor={`${id}-engine`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Engine</label>
                    <EngineSelect id={`${id}-engine`} value={engine} onChange={setEngine} />
                </div>
                {isAiEngine(engine) && (
                    <Alert type="warning" showIcon title="Every selected image is sent to a paid third-party API." />
                )}
                {usesAi && (
                    <div>
                        <label htmlFor={`${id}-prompt`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                            Prompt <Text type="secondary" style={{ fontWeight: 400 }}>(optional)</Text>
                        </label>
                        <Input.TextArea id={`${id}-prompt`} rows={4} value={prompt} maxLength={PRESET_LIMITS.promptLength} showCount
                                        placeholder="Leave empty to use the preset's prompt or the built-in one"
                                        onChange={event => setPrompt(event.target.value)} />
                    </div>
                )}
            </Space>
        </Modal>
    );
}
