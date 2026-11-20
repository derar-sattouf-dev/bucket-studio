import { Button, Result } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

interface LoadErrorProps {
    message: string;
    onRetry: () => void;
}

/** Shown in place of content whose initial load failed. */
export function LoadError({ message, onRetry }: LoadErrorProps) {
    return (
        <Result
            status="warning"
            title="Couldn't load this page"
            subTitle={message}
            extra={<Button icon={<ReloadOutlined />} onClick={onRetry}>Try again</Button>}
        />
    );
}
