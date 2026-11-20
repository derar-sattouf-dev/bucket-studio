import { Button, Card, Popconfirm, Space, Tag, Tooltip, Typography } from "antd";
import {
    CopyOutlined, DeleteOutlined, EditOutlined, ExperimentOutlined, EyeOutlined, StarOutlined,
} from "@ant-design/icons";
import type { Preset } from "../../../types/preset";
import { describePresetSteps } from "../../../utils/presetConfig";

const { Paragraph, Text } = Typography;

interface PresetCardProps {
    preset: Preset;
    canEdit: boolean;
    busy: boolean;
    onOpen: (preset: Preset) => void;
    onDuplicate: (preset: Preset) => void;
    onMakeDefault: (preset: Preset) => void;
    onDelete: (preset: Preset) => void;
    onTry: (preset: Preset) => void;
}

export function PresetCard({ preset, canEdit, busy, onOpen, onDuplicate, onMakeDefault, onDelete, onTry }: PresetCardProps) {
    const actions = [
        <Button key="try" type="link" size="small" icon={<ExperimentOutlined />} onClick={() => onTry(preset)}>Try</Button>,
        <Button key="open" type="link" size="small" icon={canEdit ? <EditOutlined /> : <EyeOutlined />} onClick={() => onOpen(preset)}>
            {canEdit ? "Edit" : "View"}
        </Button>,
    ];
    if (canEdit) {
        actions.push(
            <Button key="copy" type="link" size="small" icon={<CopyOutlined />} onClick={() => onDuplicate(preset)}>Duplicate</Button>,
            preset.is_default ? (
                <Tooltip key="delete" title="The default preset can't be deleted. Make another preset the default first.">
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} disabled aria-label={`Delete ${preset.name}`} />
                </Tooltip>
            ) : (
                <Popconfirm key="delete" title={`Delete "${preset.name}"?`} okText="Delete" okButtonProps={{ danger: true }}
                            onConfirm={() => onDelete(preset)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} loading={busy} aria-label={`Delete ${preset.name}`} />
                </Popconfirm>
            ),
        );
    }

    return (
        <Card
            size="small"
            style={{ borderRadius: 12, height: "100%", borderColor: preset.is_default ? "#87d4c9" : undefined }}
            styles={{ body: { minHeight: 150 } }}
            title={
                <Space size={8}>
                    <Text strong>{preset.name}</Text>
                    {preset.is_default && <Tag color="green">Default</Tag>}
                </Space>
            }
            extra={canEdit && !preset.is_default && (
                <Button size="small" type="text" icon={<StarOutlined />} loading={busy} onClick={() => onMakeDefault(preset)}>
                    Make default
                </Button>
            )}
            actions={actions}
        >
            <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ fontSize: 13 }}>
                {preset.description || "No description."}
            </Paragraph>
            <Space size={[4, 4]} wrap>
                {describePresetSteps(preset.config).map(step => <Tag key={step} style={{ fontSize: 11 }}>{step}</Tag>)}
            </Space>
        </Card>
    );
}
