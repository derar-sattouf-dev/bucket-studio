import { useId, useState } from "react";
import { App, Button, Drawer, Input, Space, Typography } from "antd";
import { ExperimentOutlined } from "@ant-design/icons";
import { PresetConfigEditor } from "../../../components/presetConfig/PresetConfigEditor";
import { PRESET_LIMITS } from "../../../constants/presetOptions";
import type { PresetConfig, PresetDraft } from "../../../types/preset";
import { validatePresetConfig } from "../../../utils/presetConfig";

const { Text } = Typography;

export interface EditorTarget {
    /** `null` creates a new preset. */
    id: number | null;
    initial: PresetDraft;
}

interface PresetEditorDrawerProps {
    target: EditorTarget;
    readOnly: boolean;
    saving: boolean;
    onSave: (id: number | null, draft: PresetDraft) => void;
    onTry: (config: PresetConfig) => void;
    onClose: () => void;
}

/** Create, edit or (read-only) view a preset. Mount it to open it. */
export function PresetEditorDrawer({ target, readOnly, saving, onSave, onTry, onClose }: PresetEditorDrawerProps) {
    const { modal } = App.useApp();
    const id = useId();
    const [draft, setDraft] = useState<PresetDraft>(target.initial);
    const dirty = JSON.stringify(draft) !== JSON.stringify(target.initial);

    const name = draft.name.trim();
    const configValid = validatePresetConfig(draft.config).length === 0;
    const canSave = !readOnly && dirty && name.length > 0 && configValid;

    function requestClose() {
        if (!dirty || readOnly) return onClose();
        modal.confirm({ title: "Discard your changes?", okText: "Discard", okButtonProps: { danger: true }, onOk: onClose });
    }

    const title = readOnly ? target.initial.name : target.id === null ? "New preset" : `Edit "${target.initial.name}"`;

    return (
        <Drawer
            open
            size="min(760px, 96vw)"
            title={title}
            onClose={requestClose}
            footer={
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <Button icon={<ExperimentOutlined />} onClick={() => onTry(draft.config)} disabled={!configValid}>
                        Try in Playground
                    </Button>
                    <Space>
                        <Button onClick={requestClose}>{readOnly ? "Close" : "Cancel"}</Button>
                        {!readOnly && (
                            <Button type="primary" loading={saving} disabled={!canSave}
                                    onClick={() => onSave(target.id, { ...draft, name })}>
                                Save preset
                            </Button>
                        )}
                    </Space>
                </div>
            }
        >
            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 20 }}>
                <div>
                    <label htmlFor={`${id}-name`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Name</label>
                    <Input id={`${id}-name`} value={draft.name} maxLength={PRESET_LIMITS.nameLength} disabled={readOnly}
                           status={!readOnly && name.length === 0 ? "error" : undefined}
                           onChange={event => setDraft(prev => ({ ...prev, name: event.target.value }))} />
                </div>
                <div>
                    <label htmlFor={`${id}-description`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                        Description <Text type="secondary" style={{ fontWeight: 400 }}>(optional)</Text>
                    </label>
                    <Input.TextArea id={`${id}-description`} rows={2} value={draft.description} disabled={readOnly}
                                    maxLength={PRESET_LIMITS.descriptionLength} showCount
                                    onChange={event => setDraft(prev => ({ ...prev, description: event.target.value }))} />
                </div>
            </div>
            <PresetConfigEditor
                value={draft.config}
                disabled={readOnly}
                onChange={config => setDraft(prev => ({ ...prev, config }))}
            />
        </Drawer>
    );
}
