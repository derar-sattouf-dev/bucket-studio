import { Card, Col, InputNumber, Row, Select, Space, Typography } from "antd";
import { Field } from "../../../components/Field";
import type { ObjectAcl } from "../../../types/settings";
import { humanizeSeconds } from "../../../utils/format";
import type { AdminSettingsState } from "../hooks/useAdminSettings";
import { DerivativesEditor } from "./DerivativesEditor";
import { PrefixFields } from "./PrefixFields";
import { SourceFiltersEditor } from "./SourceFiltersEditor";

const { Text } = Typography;

const ACL_OPTIONS: { value: ObjectAcl; label: string; description: string }[] = [
    { value: "", label: "None", description: "Send no ACL; the bucket policy decides (recommended, required by many providers)." },
    { value: "private", label: "private", description: "Only the bucket owner can read." },
    { value: "public-read", label: "public-read", description: "Anyone with the URL can read: for buckets served directly to a website." },
    { value: "authenticated-read", label: "authenticated-read", description: "Any authenticated account of the provider can read." },
    { value: "bucket-owner-read", label: "bucket-owner-read", description: "The bucket owner can read objects written by another account." },
    { value: "bucket-owner-full-control", label: "bucket-owner-full-control", description: "The bucket owner gets full control of objects written by another account." },
];

const CARD = { borderRadius: 12, marginBottom: 16 } as const;

export function StorageSection({ admin }: { admin: AdminSettingsState }) {
    const { values, editing, update } = admin;
    return (
        <>
            <Card size="small" title="Prefixes" style={CARD}>
                <PrefixFields values={values} editing={editing} onChange={update} />
            </Card>
            <Card size="small" title="Objects & links" style={CARD}>
                <Row gutter={[24, 20]}>
                    <Col xs={24} lg={14}>
                        <Field htmlFor="s3-acl" label="Object ACL" help="Applied to every object Bucket Studio writes.">
                            <Select<ObjectAcl>
                                id="s3-acl" value={values.s3_object_acl} disabled={!editing} style={{ width: "100%" }}
                                optionLabelProp="title" onChange={s3_object_acl => update({ s3_object_acl })}
                                options={ACL_OPTIONS.map(({ value, label, description }) => ({
                                    value, title: label,
                                    label: (
                                        <Space orientation="vertical" size={0}>
                                            <span>{label}</span>
                                            <Text type="secondary" style={{ fontSize: 11, whiteSpace: "normal" }}>{description}</Text>
                                        </Space>
                                    ),
                                }))}
                            />
                        </Field>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                            {ACL_OPTIONS.find(option => option.value === values.s3_object_acl)?.description}
                        </Text>
                    </Col>
                    <Col xs={24} lg={10}>
                        <Field htmlFor="presign-expiry" label="Preview link lifetime (seconds)"
                               help={`${humanizeSeconds(values.presign_expires_seconds)}. How long image links shown in the UI stay valid (1 min – 7 d).`}>
                            <InputNumber id="presign-expiry" min={60} max={604800} step={300} value={values.presign_expires_seconds}
                                         disabled={!editing} style={{ width: "100%" }}
                                         onChange={value => value !== null && update({ presign_expires_seconds: value })} />
                        </Field>
                    </Col>
                </Row>
            </Card>
            <Card size="small" title="Publish derivatives" style={CARD}>
                <DerivativesEditor
                    value={values.publish.derivatives}
                    extensions={values.source_filters.extensions}
                    editing={editing}
                    onChange={derivatives => update({ publish: { derivatives } })}
                />
            </Card>
            <Card size="small" title="Source filters" style={CARD}>
                <SourceFiltersEditor value={values.source_filters} editing={editing} onChange={source_filters => update({ source_filters })} />
            </Card>
        </>
    );
}
