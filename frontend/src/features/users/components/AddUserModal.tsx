import { useState } from "react";
import { App, Form, Input, Modal, Space, Switch, Typography } from "antd";
import { LockOutlined, PlusOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../../api/client";
import { createUser } from "../../../api/users";
import type { CreateUserPayload } from "../../../types/user";
import { passwordRules, usernameRules } from "../validation";

const { Text } = Typography;

interface AddUserModalProps {
    open: boolean;
    onClose: () => void;
    onCreated: () => void;
}

export function AddUserModal({ open, onClose, onCreated }: AddUserModalProps) {
    const { message } = App.useApp();
    const [form] = Form.useForm<CreateUserPayload>();
    const [submitting, setSubmitting] = useState(false);

    function close() {
        form.resetFields();
        onClose();
    }

    async function handleSubmit() {
        const values = await form.validateFields();
        setSubmitting(true);
        try {
            await createUser({ ...values, is_admin: Boolean(values.is_admin) });
            message.success(`User "${values.username}" created`);
            close();
            onCreated();
        } catch (error) {
            message.error(getErrorMessage(error, "Failed to create user"));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <Modal
            open={open}
            title={<Space><PlusOutlined /> Add User</Space>}
            onCancel={close}
            onOk={() => void handleSubmit()}
            confirmLoading={submitting}
            okText="Create user"
            width={420}
        >
            <Form form={form} layout="vertical" style={{ marginTop: 16 }} initialValues={{ is_admin: false }}>
                <Form.Item name="username" label="Username" rules={usernameRules}>
                    <Input autoFocus autoComplete="off" />
                </Form.Item>
                <Form.Item name="password" label="Password" rules={passwordRules}>
                    <Input.Password autoComplete="new-password" />
                </Form.Item>
                <Form.Item name="is_admin" label="Admin" valuePropName="checked"
                           extra={<Text type="secondary" style={{ fontSize: 12 }}>Admins can manage users and change settings.</Text>}>
                    <Switch />
                </Form.Item>
                <Form.Item name="admin_password" label={<Space><LockOutlined />Admin password</Space>}
                           rules={[{ required: true, message: "Required to confirm" }]}>
                    <Input.Password placeholder="Required to confirm" autoComplete="off" />
                </Form.Item>
            </Form>
        </Modal>
    );
}
