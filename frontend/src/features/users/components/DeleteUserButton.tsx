import { Button, Tooltip } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import type { User } from "../../../types/user";
import { AdminPasswordConfirm } from "./AdminPasswordConfirm";

interface DeleteUserButtonProps {
    user: User;
    loading: boolean;
    /** You cannot delete your own account (the server rejects it too). */
    isSelf: boolean;
    onDelete: (user: User, adminPassword: string) => void;
}

/** Delete with an inline admin-password confirmation. */
export function DeleteUserButton({ user, loading, isSelf, onDelete }: DeleteUserButtonProps) {
    if (isSelf) {
        return (
            <Tooltip title="You cannot delete your own account">
                <Button size="small" danger icon={<DeleteOutlined />} disabled aria-label="Delete user" />
            </Tooltip>
        );
    }

    return (
        <AdminPasswordConfirm
            title={`Delete "${user.username}"?`}
            okText="Delete"
            danger
            loading={loading}
            onConfirm={password => onDelete(user, password)}
        >
            <Button size="small" danger icon={<DeleteOutlined />} aria-label="Delete user" />
        </AdminPasswordConfirm>
    );
}
