import { Button, Card, Typography } from "antd";
import { PlayCircleOutlined, ThunderboltOutlined } from "@ant-design/icons";

const { Text, Title } = Typography;

/** Call-to-action shown when no job is running. */
export function StartJobCard({ loading, onStart }: { loading: boolean; onStart: () => void }) {
    return (
        <Card style={{ marginBottom: 24, borderRadius: 16, border: "1.5px dashed #d9d9d9", background: "#fafafa", textAlign: "center" }}
              styles={{ body: { padding: 40 } }}>
            <div style={{ marginBottom: 16 }}>
                <div style={{
                    width: 56, height: 56, borderRadius: "50%", background: "#e6f4ff",
                    display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px",
                }}>
                    <ThunderboltOutlined style={{ fontSize: 24, color: "#1677ff" }} />
                </div>
                <Title level={4} style={{ margin: 0 }}>No job running</Title>
                <Text type="secondary">Process every pending image under the source prefix with a preset</Text>
            </div>
            <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={onStart} size="large"
                    style={{ paddingInline: 32 }}>
                Start batch
            </Button>
        </Card>
    );
}
