import { Alert } from "antd";
import { LockOutlined } from "@ant-design/icons";

/** Shown on pages a non-admin may view but not change. */
export function ReadOnlyNotice({ message }: { message: string }) {
    return (
        <Alert
            type="info"
            showIcon
            icon={<LockOutlined />}
            title={message}
            style={{ marginBottom: 16, borderRadius: 8 }}
        />
    );
}
