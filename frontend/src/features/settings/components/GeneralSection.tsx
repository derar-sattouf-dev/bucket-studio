import { Card, Form, InputNumber, Select } from "antd";
import type { Preset } from "../../../types/preset";
import type { RuntimeSettings } from "../../../types/settings";
import { FieldDesc } from "./FieldDesc";
import { GroupDepthExample } from "./GroupDepthExample";

interface GeneralSectionProps {
    presets: Preset[];
    sourcePrefix: string;
}

export function GeneralSection({ presets, sourcePrefix }: GeneralSectionProps) {
    const groupDepth = Form.useWatch<RuntimeSettings["group_depth"]>("group_depth") ?? 0;
    return (
        <Card size="small" title="General" style={{ borderRadius: 12 }}>
            <Form.Item name="default_preset_id" label="Default preset" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                <Select options={presets.map(preset => ({ value: preset.id, label: preset.name }))} style={{ maxWidth: 420 }} />
            </Form.Item>
            <FieldDesc>Preselected for processing, batch jobs, auto-processing and the Playground.</FieldDesc>

            <Form.Item name="group_depth" label="Group depth" rules={[{ required: true }]} style={{ margin: "20px 0 0" }}>
                <InputNumber min={0} max={5} style={{ width: 160 }} />
            </Form.Item>
            <FieldDesc>How many folders after the source prefix form a group on the Images page (0 = no grouping).</FieldDesc>
            <GroupDepthExample depth={groupDepth} sourcePrefix={sourcePrefix} />
        </Card>
    );
}
