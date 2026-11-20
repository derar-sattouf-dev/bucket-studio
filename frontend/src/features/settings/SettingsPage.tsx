import { useCallback, useEffect, useState, type ReactNode } from "react";
import { App, Button, Form, Tabs } from "antd";
import { SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { getErrorMessage } from "../../api/client";
import { fetchSettings, saveRuntimeSettings } from "../../api/settings";
import { useAuth } from "../../auth/useAuth";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { SectionLoader } from "../../components/PageLoader";
import { ReadOnlyNotice } from "../../components/ReadOnlyNotice";
import { usePresets } from "../../hooks/usePresets";
import type { RuntimeSettings, Settings } from "../../types/settings";
import { AdminControls, AdminLockNotice } from "./components/AdminControls";
import { AdminPasswordModal } from "./components/AdminPasswordModal";
import { AiEnginesSection } from "./components/AiEnginesSection";
import { DangerZoneCard } from "./components/DangerZoneCard";
import { EnvironmentSection } from "./components/EnvironmentSection";
import { GeneralSection } from "./components/GeneralSection";
import { LimitsSection } from "./components/LimitsSection";
import { ResetDbModal } from "./components/ResetDbModal";
import { SecuritySection } from "./components/SecuritySection";
import { StorageSection } from "./components/StorageSection";
import { SyncSection } from "./components/SyncSection";
import { pickAdminSettings, useAdminSettings } from "./hooks/useAdminSettings";
import { useEnvironment } from "./hooks/useEnvironment";
import { SETTINGS_TABS, findTab } from "./settingsTabs";

export default function SettingsPage() {
    const { message } = App.useApp();
    const { isAdmin, isLoadingUser } = useAuth();
    const { presets, reload: reloadPresets } = usePresets();
    const { environment, error: environmentError } = useEnvironment();
    const [searchParams, setSearchParams] = useSearchParams();
    const [form] = Form.useForm<RuntimeSettings>();
    const [settings, setSettings] = useState<Settings | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [adminModalOpen, setAdminModalOpen] = useState(false);
    const [resetModalOpen, setResetModalOpen] = useState(false);
    const admin = useAdminSettings(setSettings);
    const { load: loadAdmin } = admin;
    const activeTab = findTab(searchParams.get("tab"));

    const apply = useCallback((next: Settings) => {
        setSettings(next);
        form.setFieldsValue(next);
        loadAdmin(pickAdminSettings(next));
    }, [form, loadAdmin]);

    const load = useCallback(async () => {
        try {
            apply(await fetchSettings());
            setLoadError(null);
        } catch (error) {
            setLoadError(getErrorMessage(error, "Failed to load settings"));
        }
    }, [apply]);

    useEffect(() => { void load(); }, [load]);

    async function handleSave() {
        let values: RuntimeSettings;
        try {
            values = await form.validateFields();
        } catch {
            message.error("Some fields need attention: check the highlighted tabs");
            return;
        }
        setSaving(true);
        try {
            apply(await saveRuntimeSettings(values));
            // The default preset is stored on the presets too.
            void reloadPresets();
            message.success("Settings saved");
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to save settings"));
        } finally {
            setSaving(false);
        }
    }

    if (loadError && !settings) return <PageContainer><LoadError message={loadError} onRetry={() => void load()} /></PageContainer>;
    if (!settings) return <SectionLoader />;

    const adminTab = (content: ReactNode) => <><AdminLockNotice admin={admin} canEdit={isAdmin} />{content}</>;
    const content: Record<string, ReactNode> = {
        general: <GeneralSection presets={presets} sourcePrefix={settings.source_prefix} />,
        sync: <SyncSection />,
        ai: <AiEnginesSection environment={environment} />,
        limits: <LimitsSection />,
        storage: adminTab(<StorageSection admin={admin} />),
        security: adminTab(<SecuritySection admin={admin} />),
        environment: <EnvironmentSection environment={environment} error={environmentError} />,
        danger: <DangerZoneCard canReset={isAdmin} onResetDb={() => setResetModalOpen(true)} />,
    };

    const headerAction = {
        runtime: (
            <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!isAdmin} onClick={() => void handleSave()}>
                Save changes
            </Button>
        ),
        admin: <AdminControls admin={admin} canEdit={isAdmin} onUnlock={() => setAdminModalOpen(true)} />,
        readonly: null,
    }[activeTab.kind];

    return (
        <PageContainer>
            <AdminPasswordModal
                open={adminModalOpen}
                onClose={() => setAdminModalOpen(false)}
                onVerified={password => { admin.unlock(password); setAdminModalOpen(false); }}
            />
            <ResetDbModal open={resetModalOpen} onClose={() => setResetModalOpen(false)} />

            <PageHeader
                icon={<SettingOutlined />} iconColor="#722ed1" tint="#fafaf0"
                title={`Settings · ${activeTab.label}`}
                subtitle="How the pipeline runs, where it reads and writes, and who can sign in"
                extra={headerAction}
            />

            {!isAdmin && !isLoadingUser && <ReadOnlyNotice message="Read-only: only admins can change settings." />}

            {/* One form spans the runtime tabs; forceRender keeps every field registered for validation. */}
            <Form form={form} layout="vertical" requiredMark={false} disabled={!isAdmin}>
                <Tabs
                    tabPlacement="start"
                    activeKey={activeTab.key}
                    onChange={key => setSearchParams({ tab: key }, { replace: true })}
                    items={SETTINGS_TABS.map(tab => ({
                        key: tab.key,
                        icon: <tab.Icon />,
                        label: tab.label,
                        forceRender: tab.kind === "runtime",
                        children: content[tab.key],
                    }))}
                />
            </Form>
        </PageContainer>
    );
}
