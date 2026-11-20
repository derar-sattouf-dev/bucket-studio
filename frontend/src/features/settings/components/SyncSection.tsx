import { Card, Col, Form, InputNumber, Row, Switch } from "antd";
import type { RuntimeSettings } from "../../../types/settings";
import { humanizeMinutes } from "../../../utils/format";
import { FieldDesc } from "./FieldDesc";

const FULL = { width: "100%" } as const;

export function SyncSection() {
    const interval = Form.useWatch<RuntimeSettings["sync_interval_minutes"]>("sync_interval_minutes");
    const intervalHint = interval ? `Every ${humanizeMinutes(interval)}.` : "Scheduled syncs are off.";
    return (
        <Card size="small" title="Sync & processing" style={{ borderRadius: 12 }}>
            <Row gutter={[24, 20]}>
                <Col xs={24} md={12}>
                    <Form.Item name="sync_interval_minutes" label="Sync interval (minutes)" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={0} max={1440} step={5} style={FULL} />
                    </Form.Item>
                    <FieldDesc>{intervalHint} How often the bucket is scanned for new images; 0 turns it off.</FieldDesc>
                </Col>
                <Col xs={24} md={12}>
                    <Form.Item name="auto_process_after_sync" label="Auto-process after sync" valuePropName="checked" style={{ marginBottom: 0 }}>
                        <Switch />
                    </Form.Item>
                    <FieldDesc>Process newly discovered images with the default preset right after each sync.</FieldDesc>
                </Col>
                <Col xs={24} md={8}>
                    <Form.Item name="process_concurrency" label="Parallel local jobs" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={1} max={16} style={FULL} />
                    </Form.Item>
                    <FieldDesc>1–16. Keep at 2–4 to avoid memory pressure.</FieldDesc>
                </Col>
                <Col xs={24} md={8}>
                    <Form.Item name="ai_concurrency" label="Parallel AI calls" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={1} max={10} style={FULL} />
                    </Form.Item>
                    <FieldDesc>1–10. Keep low to stay under API rate limits.</FieldDesc>
                </Col>
                <Col xs={24} md={8}>
                    <Form.Item name="max_retry_count" label="Max retries" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                        <InputNumber min={0} max={999} style={FULL} />
                    </Form.Item>
                    <FieldDesc>How often "Retry failed" re-queues the same image (0–999).</FieldDesc>
                </Col>
            </Row>
        </Card>
    );
}
