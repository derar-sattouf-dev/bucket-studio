import { useState } from "react";
import { Input, Modal, Space, Typography } from "antd";
import { LockOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../../api/client";
import { verifyAdminPassword } from "../../../api/settings";

const { Text } = Typography;

interface AdminPasswordModalProps {
    open: boolean;
    onClose: () => void;
    onVerified: (password: string) => void;
}

/** Step-up check: verifies ADMIN_PASSWORD before admin settings can be edited. */
export function AdminPasswordModal({ open, onClose, onVerified }: AdminPasswordModalProps) {
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    function reset() {
        setPassword("");
        setError("");
    }

    async function handleVerify() {
        if (!password) {
            setError("Please enter the admin password");
            return;
        }
        setLoading(true);
        setError("");
        try {
            await verifyAdminPassword(password);
            onVerified(password);
            reset();
        } catch (e) {
            setError(getErrorMessage(e, "Incorrect admin password"));
        } finally {
            setLoading(false);
        }
    }

    return (
        <Modal open={open} title={<Space><LockOutlined />Admin verification</Space>}
               onCancel={() => { reset(); onClose(); }}
               onOk={() => void handleVerify()} okText="Unlock" confirmLoading={loading} width={400}>
            <Space orientation="vertical" style={{ width: "100%" }} size={8}>
                <Text type="secondary">Enter the admin password to edit prefixes, publish derivatives and source filters.</Text>
                <Input.Password placeholder="Admin password" aria-label="Admin password" value={password} autoFocus autoComplete="off"
                                onChange={e => { setPassword(e.target.value); setError(""); }}
                                onPressEnter={() => void handleVerify()} />
                {error && <Text type="danger" style={{ fontSize: 12 }}>{error}</Text>}
            </Space>
        </Modal>
    );
}
