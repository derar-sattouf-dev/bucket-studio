import { useCallback, useState } from "react";
import { App } from "antd";
import { getErrorMessage } from "../../../api/client";
import { saveAdminSettings } from "../../../api/settings";
import type { AdminSettings, Settings } from "../../../types/settings";
import { validateDerivative } from "../derivatives";
import { normalisePrefix, validatePrefixes } from "../prefixValidation";

const EMPTY: AdminSettings = {
    source_prefix: "", output_prefix: "", backup_prefix: "",
    publish: { derivatives: [] },
    source_filters: { extensions: [], exclude_globs: [] },
    s3_object_acl: "",
    presign_expires_seconds: 3600,
    session_minutes: 720,
    login_max_attempts: 5,
    login_lockout_minutes: 15,
};

export const pickAdminSettings = (settings: Settings): AdminSettings => ({
    source_prefix: settings.source_prefix,
    output_prefix: settings.output_prefix,
    backup_prefix: settings.backup_prefix,
    publish: settings.publish,
    source_filters: settings.source_filters,
    s3_object_acl: settings.s3_object_acl,
    presign_expires_seconds: settings.presign_expires_seconds,
    session_minutes: settings.session_minutes,
    login_max_attempts: settings.login_max_attempts,
    login_lockout_minutes: settings.login_lockout_minutes,
});

function normalise(draft: AdminSettings): AdminSettings {
    return {
        ...draft,
        source_prefix: normalisePrefix(draft.source_prefix),
        output_prefix: normalisePrefix(draft.output_prefix),
        backup_prefix: normalisePrefix(draft.backup_prefix),
        source_filters: {
            extensions: [...new Set(draft.source_filters.extensions.map(ext => ext.trim().toLowerCase().replace(/^\./, "")).filter(Boolean))],
            exclude_globs: draft.source_filters.exclude_globs.map(glob => glob.trim()).filter(Boolean),
        },
    };
}

function firstProblem(settings: AdminSettings): string | null {
    const prefixProblem = validatePrefixes(settings);
    if (prefixProblem) return prefixProblem;
    if (settings.source_filters.extensions.length === 0) return "Add at least one source file extension.";
    const { derivatives } = settings.publish;
    for (const derivative of derivatives) {
        const problem = validateDerivative(derivative, derivatives, settings.source_filters.extensions);
        if (problem) return `Derivative "${derivative.name}": ${problem}`;
    }
    return null;
}

/**
 * Admin settings guarded by the admin password: editing is unlocked after the password is
 * verified, and the password is kept only in memory until save or cancel.
 */
export function useAdminSettings(onSaved: (settings: Settings) => void) {
    const { message } = App.useApp();
    const [saved, setSaved] = useState<AdminSettings>(EMPTY);
    const [draft, setDraft] = useState<AdminSettings>(EMPTY);
    const [adminPassword, setAdminPassword] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    const editing = adminPassword !== null;

    const load = useCallback((settings: AdminSettings) => {
        setSaved(settings);
        setDraft(settings);
    }, []);

    function unlock(password: string) {
        setAdminPassword(password);
        message.success("Unlocked: you can now edit the admin settings");
    }

    function cancel() {
        setDraft(saved);
        setAdminPassword(null);
    }

    const update = (patch: Partial<AdminSettings>) => setDraft(prev => ({ ...prev, ...patch }));

    async function save() {
        if (adminPassword === null) return;
        const normalised = normalise(draft);
        setDraft(normalised);
        const problem = firstProblem(normalised);
        if (problem) {
            message.error(problem);
            return;
        }
        setSaving(true);
        try {
            const updated = await saveAdminSettings(normalised, adminPassword);
            load(pickAdminSettings(updated));
            setAdminPassword(null);
            onSaved(updated);
            message.success("Admin settings saved");
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to save"));
        } finally {
            setSaving(false);
        }
    }

    return { values: editing ? draft : saved, editing, saving, load, unlock, cancel, update, save };
}

export type AdminSettingsState = ReturnType<typeof useAdminSettings>;
