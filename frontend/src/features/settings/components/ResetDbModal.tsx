import { useState } from "react";
import { App, Input, Modal, Space, Typography } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../../api/client";
import { resetDatabase } from "../../../api/settings";

const { Text } = Typography;

const CONFIRM_WORD = "RESET";

/** Destructive: requires typing RESET plus the admin password. */
export function ResetDbModal({ open, onClose }: { open: boolean; onClose: () => void }) {
    const { message } = App.useApp();
    const [confirmText, setConfirmText] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const confirmed = confirmText === CONFIRM_WORD;

    function close() {
        setConfirmText("");
        setPassword("");
        setError("");
        onClose();
    }

    async function handleReset() {
        if (!confirmed) return;
        if (!password) {
            setError("Please enter the admin password");
            return;
        }
        setLoading(true);
        setError("");
        try {
            await resetDatabase(password);
            message.success("Database reset successfully");
            close();
        } catch (e) {
            setError(getErrorMessage(e, "Reset failed"));
        } finally {
            setLoading(false);
        }
    }

    return (
        <Modal open={open}
               title={<Space><DeleteOutlined style={{ color: "#ff4d4f" }} />Reset Database</Space>}
               onCancel={close}
               onOk={() => void handleReset()} okText="Reset Database"
               okButtonProps={{ danger: true, loading, disabled: !confirmed }} width={400}>
            <Space orientation="vertical" style={{ width: "100%" }} size={8}>
                <Text type="danger" strong>This permanently deletes all image records. This cannot be undone.</Text>
                <Text type="secondary">S3 files are not affected. Type <Text code>{CONFIRM_WORD}</Text> and enter the admin password to confirm.</Text>
                <Input placeholder={`Type ${CONFIRM_WORD} to confirm`} aria-label={`Type ${CONFIRM_WORD} to confirm`} value={confirmText} autoFocus autoComplete="off"
                       onChange={e => { setConfirmText(e.target.value); setError(""); }} />
                <Input.Password placeholder="Admin password" aria-label="Admin password" value={password} autoComplete="off"
                                onChange={e => { setPassword(e.target.value); setError(""); }}
                                onPressEnter={() => void handleReset()} />
                {error && <Text type="danger" style={{ fontSize: 12 }}>{error}</Text>}
            </Space>
        </Modal>
    );
}
