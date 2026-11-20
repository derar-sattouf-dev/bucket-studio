import { Alert, Card, Col, Form, InputNumber, Row } from "antd";
import { FieldDesc } from "./FieldDesc";

const FULL = { width: "100%" } as const;

export function LimitsSection() {
    return (
        <Card size="small" title="Limits" style={{ borderRadius: 12 }}>
            <Row gutter={[24, 20]}>
                <Col xs={24} md={8}>
                    <Form.Item name="max_upload_mb" label="Max upload (MB)" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={1} max={200} style={FULL} />
                    </Form.Item>
                    <FieldDesc>Largest file accepted by the Playground upload (1–200).</FieldDesc>
                </Col>
                <Col xs={24} md={8}>
                    <Form.Item name="max_remote_fetch_mb" label="Max URL download (MB)" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={1} max={200} style={FULL} />
                    </Form.Item>
                    <FieldDesc>Largest image fetched from a URL by Import and the Playground (1–200).</FieldDesc>
                </Col>
                <Col xs={24} md={8}>
                    <Form.Item name="max_image_megapixels" label="Max image size (megapixels)" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={1} max={500} style={FULL} />
                    </Form.Item>
                    <FieldDesc>Bigger images are refused, which protects memory from decompression bombs (1–500).</FieldDesc>
                </Col>
            </Row>
            <Alert
                type="warning" showIcon style={{ marginTop: 20 }}
                title="Keep the proxy limit above the upload limit"
                description="nginx rejects larger request bodies before they reach the API. If you raise the upload limit, raise CLIENT_MAX_BODY_SIZE in .env too."
            />
        </Card>
    );
}
