import { useCallback, useEffect, useState } from "react";
import { App, Button, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PlusOutlined, ReloadOutlined, TeamOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../api/client";
import { deleteUser, fetchUsers, setUserActive } from "../../api/users";
import { useAuth } from "../../auth/useAuth";
import { LoadError } from "../../components/LoadError";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import type { User } from "../../types/user";
import { AddUserModal } from "./components/AddUserModal";
import { DeleteUserButton } from "./components/DeleteUserButton";
import { ToggleActiveButton } from "./components/ToggleActiveButton";

const { Text } = Typography;

export default function UsersPage() {
    const { message } = App.useApp();
    const { currentUser } = useAuth();
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [addOpen, setAddOpen] = useState(false);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [togglingId, setTogglingId] = useState<number | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setUsers(await fetchUsers());
            setError(null);
        } catch (e) {
            const text = getErrorMessage(e, "Failed to load users");
            setError(text);
            message.error(text);
        } finally {
            setLoading(false);
        }
    }, [message]);

    useEffect(() => { void load(); }, [load]);

    async function handleDelete(user: User, adminPassword: string) {
        setDeletingId(user.id);
        try {
            await deleteUser(user.id, adminPassword);
            message.success(`User "${user.username}" deleted`);
            await load();
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to delete user"));
        } finally {
            setDeletingId(null);
        }
    }

    async function handleToggleActive(user: User, isActive: boolean, adminPassword: string) {
        setTogglingId(user.id);
        try {
            await setUserActive(user.id, isActive, adminPassword);
            message.success(`User "${user.username}" ${isActive ? "activated" : "deactivated"}`);
            await load();
        } catch (error) {
            message.error(getErrorMessage(error, `Failed to ${isActive ? "activate" : "deactivate"} user`));
        } finally {
            setTogglingId(null);
        }
    }

    const columns: ColumnsType<User> = [
        { title: "Username", dataIndex: "username", render: (username: string) => <Text strong>{username}</Text> },
        {
            title: "Role",
            dataIndex: "is_admin",
            width: 100,
            render: (isAdmin: boolean) => (isAdmin ? <Tag color="gold">Admin</Tag> : <Tag>User</Tag>),
        },
        {
            title: "Status",
            dataIndex: "is_active",
            width: 100,
            render: (active: boolean) => <Tag color={active ? "success" : "default"}>{active ? "Active" : "Inactive"}</Tag>,
        },
        { title: "Created", dataIndex: "created_at", render: (date: string) => new Date(date).toLocaleDateString() },
        {
            title: "",
            width: 170,
            render: (_, user) => {
                const isSelf = user.username === currentUser?.username;
                return (
                    <Space size="small">
                        <ToggleActiveButton user={user} loading={togglingId === user.id}
                                            isSelf={isSelf} onToggle={handleToggleActive} />
                        <DeleteUserButton user={user} loading={deletingId === user.id}
                                          isSelf={isSelf} onDelete={handleDelete} />
                    </Space>
                );
            },
        },
    ];

    if (error && users.length === 0) return <PageContainer><LoadError message={error} onRetry={() => void load()} /></PageContainer>;

    return (
        <PageContainer>
            <AddUserModal open={addOpen} onClose={() => setAddOpen(false)} onCreated={() => void load()} />

            <PageHeader
                icon={<TeamOutlined />} iconColor="#1677ff" tint="#f0f9ff"
                title="Users" subtitle="Who can sign in to Bucket Studio"
                extra={
                    <Space>
                        <Button icon={<ReloadOutlined />} onClick={() => void load()} style={{ borderRadius: 8 }}>Refresh</Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)} style={{ borderRadius: 8 }}>
                            Add user
                        </Button>
                    </Space>
                }
            />

            <Table<User>
                dataSource={users}
                columns={columns}
                rowKey="id"
                loading={loading}
                size="small"
                pagination={false}
                locale={{ emptyText: "No users — the admin account from config is always available." }}
            />
        </PageContainer>
    );
}
