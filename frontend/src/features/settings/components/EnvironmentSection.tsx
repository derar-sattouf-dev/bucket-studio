import { Alert, Card, Descriptions, Typography } from "antd";
import { SectionLoader } from "../../../components/PageLoader";
import type { EnvironmentInfo } from "../../../types/settings";
import { ConfiguredBadge } from "./ConfiguredBadge";

const { Text } = Typography;

const code = (value: string | null) => (value ? <Text code>{value}</Text> : <Text type="secondary">—</Text>);

export function EnvironmentSection({ environment, error }: { environment: EnvironmentInfo | null; error: string | null }) {
    if (error) return <Alert type="warning" showIcon title="Environment info unavailable" description={error} />;
    if (!environment) return <SectionLoader />;
    return (
        <Card size="small" title="Environment" style={{ borderRadius: 12 }}>
            <Alert
                type="info" showIcon style={{ marginBottom: 16 }}
                title="Read-only"
                description="These values come from .env (or the container environment). Change them there and restart the backend."
            />
            <Descriptions size="small" bordered column={{ xs: 1, lg: 2 }}>
                <Descriptions.Item label="App name">{environment.app_name}</Descriptions.Item>
                <Descriptions.Item label="Version">{code(environment.version)}</Descriptions.Item>
                <Descriptions.Item label="Bucket">{code(environment.s3_bucket)}</Descriptions.Item>
                <Descriptions.Item label="S3 endpoint">{code(environment.s3_endpoint_host)}</Descriptions.Item>
                <Descriptions.Item label="Public endpoint">{code(environment.s3_public_endpoint_host)}</Descriptions.Item>
                <Descriptions.Item label="API docs (/docs)">
                    <ConfiguredBadge ok={environment.api_docs_enabled} yes="Enabled" no="Disabled" />
                </Descriptions.Item>
                <Descriptions.Item label="OpenAI key"><ConfiguredBadge ok={environment.openai_configured} /></Descriptions.Item>
                <Descriptions.Item label="Gemini key"><ConfiguredBadge ok={environment.gemini_configured} /></Descriptions.Item>
                <Descriptions.Item label="Models folder">
                    <ConfiguredBadge ok={environment.models_dir_writable} yes="Writable" no="Not writable: models can't download" />
                </Descriptions.Item>
            </Descriptions>
        </Card>
    );
}
