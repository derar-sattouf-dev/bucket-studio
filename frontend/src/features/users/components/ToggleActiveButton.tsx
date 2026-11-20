import { Button, Tooltip } from "antd";
import type { User } from "../../../types/user";
import { AdminPasswordConfirm } from "./AdminPasswordConfirm";

interface ToggleActiveButtonProps {
    user: User;
    loading: boolean;
    /** You cannot deactivate your own account (the server rejects it too). */
    isSelf: boolean;
    onToggle: (user: User, isActive: boolean, adminPassword: string) => void;
}

/** Activate or deactivate a user, with an inline admin-password confirmation. */
export function ToggleActiveButton({ user, loading, isSelf, onToggle }: ToggleActiveButtonProps) {
    const label = user.is_active ? "Deactivate" : "Activate";

    if (isSelf && user.is_active) {
        return (
            <Tooltip title="You cannot deactivate your own account">
                <Button size="small" disabled>{label}</Button>
            </Tooltip>
        );
    }

    return (
        <AdminPasswordConfirm
            title={
                user.is_active
                    ? `Deactivate "${user.username}"? They are signed out at once and cannot sign in.`
                    : `Activate "${user.username}"? They can sign in again.`
            }
            okText={label}
            danger={user.is_active}
            loading={loading}
            onConfirm={password => onToggle(user, !user.is_active, password)}
        >
            <Button size="small" loading={loading}>{label}</Button>
        </AdminPasswordConfirm>
    );
}
