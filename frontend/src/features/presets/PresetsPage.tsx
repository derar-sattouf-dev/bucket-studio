import { useState } from "react";
import { Button, Col, Empty, Row } from "antd";
import { AppstoreOutlined, PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/useAuth";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { SectionLoader } from "../../components/PageLoader";
import { ReadOnlyNotice } from "../../components/ReadOnlyNotice";
import { usePresets } from "../../hooks/usePresets";
import type { Preset, PresetConfig } from "../../types/preset";
import { DEFAULT_PRESET_CONFIG, withDefaults } from "../../utils/presetConfig";
import { playgroundLink, playgroundState } from "../playground/playgroundNavigation";
import { PresetCard } from "./components/PresetCard";
import { PresetEditorDrawer, type EditorTarget } from "./components/PresetEditorDrawer";
import { usePresetActions } from "./hooks/usePresetActions";

const NEW_PRESET: EditorTarget = {
    id: null,
    initial: { name: "", description: "", config: DEFAULT_PRESET_CONFIG },
};

const editTarget = (preset: Preset): EditorTarget => ({
    id: preset.id,
    initial: { name: preset.name, description: preset.description, config: withDefaults(preset.config) },
});

const duplicateTarget = (preset: Preset): EditorTarget => ({
    id: null,
    initial: { ...editTarget(preset).initial, name: `${preset.name} (copy)`.slice(0, 64) },
});

/** Reusable processing recipes. Everyone can read and try them; admins can change them. */
export default function PresetsPage() {
    const navigate = useNavigate();
    const { isAdmin, isLoadingUser } = useAuth();
    const { presets, loading, error, reload } = usePresets();
    const actions = usePresetActions(reload);
    const [editor, setEditor] = useState<EditorTarget | null>(null);

    const tryConfig = (config: PresetConfig) => navigate("/playground", { state: playgroundState(config) });

    async function handleSave(id: number | null, draft: EditorTarget["initial"]) {
        if (await actions.save(id, draft)) setEditor(null);
    }

    function renderBody() {
        if (loading && presets.length === 0) return <SectionLoader />;
        if (error && presets.length === 0) return <LoadError message={error} onRetry={() => void reload()} />;
        if (presets.length === 0) return <Empty description="No presets yet." style={{ padding: 40 }} />;
        return (
            <Row gutter={[16, 16]}>
                {presets.map(preset => (
                    <Col key={preset.id} xs={24} md={12} xxl={8}>
                        <PresetCard
                            preset={preset}
                            canEdit={isAdmin}
                            busy={actions.pendingId === preset.id}
                            onOpen={p => setEditor(editTarget(p))}
                            onDuplicate={p => setEditor(duplicateTarget(p))}
                            onMakeDefault={p => void actions.makeDefault(p)}
                            onDelete={p => void actions.remove(p)}
                            onTry={p => navigate(playgroundLink(p.id))}
                        />
                    </Col>
                ))}
            </Row>
        );
    }

    return (
        <PageContainer>
            <PageHeader
                icon={<AppstoreOutlined />} iconColor="#722ed1" tint="#f9f0ff"
                title="Presets"
                subtitle="Recipes for processing: background, crop, upscale, canvas and output. The default one is preselected everywhere."
                extra={isAdmin && (
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditor(NEW_PRESET)}>New preset</Button>
                )}
            />
            {!isAdmin && !isLoadingUser && <ReadOnlyNotice message="Read-only: only admins can change presets. You can still try them in the Playground." />}

            {renderBody()}

            {editor && (
                <PresetEditorDrawer
                    target={editor}
                    readOnly={!isAdmin}
                    saving={actions.saving}
                    onSave={(id, draft) => void handleSave(id, draft)}
                    onTry={tryConfig}
                    onClose={() => setEditor(null)}
                />
            )}
        </PageContainer>
    );
}
