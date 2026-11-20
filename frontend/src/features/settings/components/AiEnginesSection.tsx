import { Alert, Card, Col, Form, Input, Row, Space, Typography } from "antd";
import type { EnvironmentInfo } from "../../../types/settings";
import { ConfiguredBadge } from "./ConfiguredBadge";
import { FieldDesc } from "./FieldDesc";

const { Text } = Typography;

const MODEL_RULES = [
    { required: true, message: "Enter a model name" },
    { max: 100, message: "At most 100 characters" },
    { pattern: /^[A-Za-z0-9._:/-]+$/, message: 'Letters, digits and . _ : / - only' },
];

const ENGINES = [
    { name: "openai_image_model", label: "OpenAI", envKey: "OPENAI_API_KEY", configured: (env: EnvironmentInfo) => env.openai_configured },
    { name: "gemini_image_model", label: "Gemini", envKey: "GEMINI_API_KEY", configured: (env: EnvironmentInfo) => env.gemini_configured },
] as const;

export function AiEnginesSection({ environment }: { environment: EnvironmentInfo | null }) {
    return (
        <Card size="small" title="AI engines" style={{ borderRadius: 12 }}>
            <Alert
                type="info" showIcon style={{ marginBottom: 20 }}
                title="API keys live in .env, not here"
                description="Keys are secrets, so they are never stored in the database or shown in the browser. Set them in .env and restart the backend; an engine without a key is unavailable."
            />
            <Row gutter={[24, 20]}>
                {ENGINES.map(({ name, label, envKey, configured }) => (
                    <Col xs={24} md={12} key={name}>
                        <Space size={8} style={{ marginBottom: 8 }}>
                            <Text strong>{label}</Text>
                            {environment && <ConfiguredBadge ok={configured(environment)} yes="Key configured" no={`No ${envKey}`} />}
                        </Space>
                        <Form.Item name={name} label="Image model" rules={MODEL_RULES} style={{ marginBottom: 0 }}>
                            <Input autoComplete="off" spellCheck={false} />
                        </Form.Item>
                        <FieldDesc>Model id passed to the {label} image API.</FieldDesc>
                    </Col>
                ))}
            </Row>
        </Card>
    );
}
