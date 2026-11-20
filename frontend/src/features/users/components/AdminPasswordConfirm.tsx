import { useState, type ReactNode } from "react";
import { Input, Popconfirm, Typography } from "antd";

const { Text } = Typography;

interface AdminPasswordConfirmProps {
    title: string;
    okText: string;
    danger?: boolean;
    loading: boolean;
    /** Called with the admin (step-up) password once the action is confirmed. */
    onConfirm: (adminPassword: string) => void;
    /** The button that opens the confirmation. */
    children: ReactNode;
}

/** Inline confirmation that asks for the admin password, for the user actions that need the step-up. */
export function AdminPasswordConfirm({ title, okText, danger, loading, onConfirm, children }: AdminPasswordConfirmProps) {
    const [open, setOpen] = useState(false);
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");

    function reset() {
        setPassword("");
        setError("");
    }

    function confirm() {
        if (!password) {
            setError("Enter admin password");
            return;
        }
        onConfirm(password);
        reset();
        setOpen(false);
    }

    return (
        <Popconfirm
            open={open}
            onOpenChange={next => { setOpen(next); if (!next) reset(); }}
            title={title}
            description={
                <div style={{ marginTop: 8 }}>
                    <Input.Password
                        placeholder="Admin password"
                        value={password}
                        autoComplete="off"
                        onChange={e => { setPassword(e.target.value); setError(""); }}
                        onPressEnter={confirm}
                        size="small"
                    />
                    {error && <Text type="danger" style={{ fontSize: 11 }}>{error}</Text>}
                </div>
            }
            onConfirm={confirm}
            okText={okText}
            okButtonProps={{ danger, loading }}
        >
            {children}
        </Popconfirm>
    );
}
