import { useState } from "react";
import { Button, Input, Space, Tag, Typography } from "antd";
import { EditOutlined, TagOutlined } from "@ant-design/icons";
import type { ImageRecord } from "../../../types/image";
import { parseTags } from "../imageUtils";

const { Text } = Typography;

interface NotesEditorProps {
    image: ImageRecord;
    onSave: (key: string, notes: string | null, tags: string | null) => Promise<void>;
}

/** Inline display + editor for an image's free-text note and comma-separated tags. */
export function NotesEditor({ image, onSave }: NotesEditorProps) {
    const [editing, setEditing] = useState(false);
    const [notes, setNotes] = useState(image.notes ?? "");
    const [tags, setTags] = useState(image.tags ?? "");
    const [saving, setSaving] = useState(false);

    async function handleSave() {
        setSaving(true);
        try {
            await onSave(image.source_key, notes || null, tags || null);
            setEditing(false);
        } finally {
            setSaving(false);
        }
    }

    function handleCancel() {
        setEditing(false);
        setNotes(image.notes ?? "");
        setTags(image.tags ?? "");
    }

    if (!editing) {
        return (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                {parseTags(image.tags).map(tag => (
                    <Tag key={tag} icon={<TagOutlined />} color="geekblue" style={{ fontSize: 11 }}>{tag}</Tag>
                ))}
                {image.notes && <Text type="secondary" style={{ fontSize: 11 }}>{image.notes}</Text>}
                <Button size="small" type="link" icon={<EditOutlined />} onClick={() => setEditing(true)}
                        style={{ padding: 0, fontSize: 11 }}>
                    {image.notes || image.tags ? "Edit" : "Add note"}
                </Button>
            </div>
        );
    }

    return (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            <Input size="small" placeholder="Tags (comma separated)" aria-label="Tags" value={tags} onChange={e => setTags(e.target.value)}
                   prefix={<TagOutlined style={{ color: "#aaa" }} />} />
            <Input.TextArea size="small" rows={2} placeholder="Notes…" aria-label="Notes" value={notes} onChange={e => setNotes(e.target.value)} />
            <Space size={4}>
                <Button size="small" type="primary" loading={saving} onClick={handleSave}>Save</Button>
                <Button size="small" onClick={handleCancel}>Cancel</Button>
            </Space>
        </div>
    );
}
