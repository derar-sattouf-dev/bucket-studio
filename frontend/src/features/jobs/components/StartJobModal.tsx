import { useId, useState } from "react";
import { Alert, Modal, Space, Switch, Tag, Typography } from "antd";
import { PlayCircleOutlined } from "@ant-design/icons";
import { PresetSelect } from "../../../components/PresetSelect";
import type { StartJobRequest } from "../../../types/job";
import type { Preset } from "../../../types/preset";
import { describePresetSteps } from "../../../utils/presetConfig";

const { Text } = Typography;

interface StartJobModalProps {
    presets: Preset[];
    presetsLoading: boolean;
    /** Overwriting originals without a backup is admin only. */
    canOverwrite: boolean;
    loading: boolean;
    onConfirm: (request: StartJobRequest) => void;
    onCancel: () => void;
}

/** Pick the preset for a batch run. Mount it to open it. */
export function StartJobModal({ presets, presetsLoading, canOverwrite, loading, onConfirm, onCancel }: StartJobModalProps) {
    const id = useId();
    const [chosenPresetId, setPresetId] = useState<number | null>(null);
    const [overwrite, setOverwrite] = useState(false);
    const presetId = chosenPresetId ?? presets.find(preset => preset.is_default)?.id ?? null;
    const preset = presets.find(candidate => candidate.id === presetId);

    return (
        <Modal
            open
            title={<Space><PlayCircleOutlined />Start a batch job</Space>}
            onOk={() => onConfirm({ presetId, overwrite })}
            onCancel={onCancel}
            okText="Start"
            okButtonProps={{ danger: overwrite, disabled: presetId === null }}
            confirmLoading={loading}
            width={520}
        >
            <Space orientation="vertical" style={{ width: "100%", marginTop: 8 }} size={16}>
                <Text type="secondary">Processes every pending image under the source prefix with one preset.</Text>
                <div>
                    <label htmlFor={`${id}-preset`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Preset</label>
                    <PresetSelect id={`${id}-preset`} presets={presets} value={presetId} onChange={setPresetId} loading={presetsLoading} />
                    {preset && (
                        <Space size={[4, 4]} wrap style={{ marginTop: 8 }}>
                            {describePresetSteps(preset.config).map(step => <Tag key={step} style={{ fontSize: 11 }}>{step}</Tag>)}
                        </Space>
                    )}
                </div>
                {canOverwrite && (
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                        <Switch checked={overwrite} onChange={setOverwrite} aria-label="Overwrite originals without backup" />
                        <div>
                            <Text strong>Overwrite originals directly</Text>
                            <Text type="secondary" style={{ display: "block", fontSize: 12 }}>
                                Writes results over the source files with no backup and no review step.
                            </Text>
                        </div>
                    </div>
                )}
                {overwrite && (
                    <Alert type="error" showIcon title="Originals will be replaced and cannot be restored from Bucket Studio." />
                )}
            </Space>
        </Modal>
    );
}
