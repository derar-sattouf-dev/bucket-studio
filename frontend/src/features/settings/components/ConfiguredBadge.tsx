import { Tag } from "antd";
import { CheckCircleOutlined, MinusCircleOutlined } from "@ant-design/icons";

/** Yes/no status of something configured in `.env`. */
export function ConfiguredBadge({ ok, yes = "Configured", no = "Not configured" }: { ok: boolean; yes?: string; no?: string }) {
    return ok
        ? <Tag color="success" icon={<CheckCircleOutlined />}>{yes}</Tag>
        : <Tag icon={<MinusCircleOutlined />}>{no}</Tag>;
}
