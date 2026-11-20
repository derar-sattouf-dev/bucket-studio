import { Button, Card, Space, Steps, Typography } from "antd";
import { ExperimentOutlined, ImportOutlined, SyncOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

const { Paragraph, Title } = Typography;

interface GettingStartedCardProps {
    syncing: boolean;
    onSync: () => void;
}

/** Shown instead of the statistics on a fresh install with no images. */
export function GettingStartedCard({ syncing, onSync }: GettingStartedCardProps) {
    const navigate = useNavigate();
    return (
        <Card style={{ borderRadius: 12, marginBottom: 20 }} styles={{ body: { padding: 28 } }}>
            <Title level={4} style={{ marginTop: 0 }}>Welcome! Let's get some images in</Title>
            <Paragraph type="secondary" style={{ maxWidth: 720 }}>
                Bucket Studio works on the images under your bucket's source prefix. Add them in one of two ways,
                then process them with a preset, review the results and publish.
            </Paragraph>
            <Steps
                orientation="vertical"
                size="small"
                current={-1}
                style={{ maxWidth: 720, margin: "16px 0" }}
                items={[
                    {
                        title: "Sync the bucket",
                        content: "Lists every image under the source prefix (set it in Settings) and queues it as pending.",
                    },
                    {
                        title: "Or import from URLs",
                        content: "Paste up to 100 image URLs; they are downloaded into a folder of the source prefix.",
                    },
                    {
                        title: "Try a preset in the Playground",
                        content: "Upload a single image to see what a preset does before running it on the whole bucket.",
                    },
                ]}
            />
            <Space wrap>
                <Button type="primary" icon={<SyncOutlined />} loading={syncing} onClick={onSync}>Sync bucket</Button>
                <Button icon={<ImportOutlined />} onClick={() => navigate("/import")}>Import from URLs</Button>
                <Button icon={<ExperimentOutlined />} onClick={() => navigate("/playground")}>Open the Playground</Button>
            </Space>
        </Card>
    );
}
