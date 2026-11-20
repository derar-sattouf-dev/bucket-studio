import { Col, Input, Row, Typography } from "antd";
import type { BucketPrefixes } from "../../../types/settings";
import { PREFIX_LABELS } from "../prefixValidation";
import { FieldDesc } from "./FieldDesc";

const { Text } = Typography;

const FIELDS: { key: keyof BucketPrefixes; placeholder: string; description: string }[] = [
    { key: "source_prefix", placeholder: "e.g. images/", description: "Folder scanned for source images. Takes effect on the next sync." },
    { key: "output_prefix", placeholder: "e.g. processed/", description: "Where processed results are written before publishing." },
    { key: "backup_prefix", placeholder: "e.g. backup/", description: "Where originals are copied before publishing replaces them." },
];

interface PrefixFieldsProps {
    values: BucketPrefixes;
    editing: boolean;
    onChange: (patch: Partial<BucketPrefixes>) => void;
}

export function PrefixFields({ values, editing, onChange }: PrefixFieldsProps) {
    return (
        <Row gutter={16}>
            {FIELDS.map(({ key, placeholder, description }) => (
                <Col xs={24} md={8} key={key}>
                    <Text strong style={{ fontSize: 13 }}><label htmlFor={`prefix-${key}`}>{PREFIX_LABELS[key]}</label></Text>
                    <Input id={`prefix-${key}`} value={values[key]} onChange={e => onChange({ [key]: e.target.value })}
                           disabled={!editing} placeholder={placeholder} style={{ marginTop: 6 }} />
                    <FieldDesc>{description}</FieldDesc>
                </Col>
            ))}
        </Row>
    );
}
