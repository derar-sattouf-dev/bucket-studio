import { Alert, Button, Space } from "antd";
import { CheckOutlined, LockOutlined } from "@ant-design/icons";
import type { AdminSettingsState } from "../hooks/useAdminSettings";

interface AdminControlsProps {
    admin: AdminSettingsState;
    canEdit: boolean;
    onUnlock: () => void;
}

/** Unlock / Save / Cancel for the password-protected sections (shown in the page header). */
export function AdminControls({ admin, canEdit, onUnlock }: AdminControlsProps) {
    if (!admin.editing) {
        return <Button icon={<LockOutlined />} onClick={onUnlock} disabled={!canEdit}>Unlock to edit</Button>;
    }
    return (
        <Space>
            <Button onClick={admin.cancel}>Cancel</Button>
            <Button type="primary" icon={<CheckOutlined />} loading={admin.saving} onClick={() => void admin.save()}>Save</Button>
        </Space>
    );
}

/** Explains the step-up while the protected sections are locked. */
export function AdminLockNotice({ admin, canEdit }: Omit<AdminControlsProps, "onUnlock">) {
    if (admin.editing || !canEdit) return null;
    return (
        <Alert
            type="warning" showIcon icon={<LockOutlined />} style={{ marginBottom: 16 }}
            title="Protected settings"
            description='These change where files go and who can get in, so they need the admin password. Use "Unlock to edit" at the top. Unlocking covers both Storage & publishing and Security.'
        />
    );
}
