import { Col, Row, Select, Typography } from "antd";
import type { SourceFilters } from "../../../types/settings";
import { SOURCE_EXTENSIONS } from "../derivatives";
import { FieldDesc } from "./FieldDesc";

const { Text } = Typography;

interface SourceFiltersEditorProps {
    value: SourceFilters;
    editing: boolean;
    onChange: (value: SourceFilters) => void;
}

/** Which files under the source prefix a sync picks up. */
export function SourceFiltersEditor({ value, editing, onChange }: SourceFiltersEditorProps) {
    return (
        <Row gutter={16}>
            <Col xs={24} md={12}>
                <Text strong style={{ fontSize: 13 }}><label htmlFor="source-extensions">File extensions</label></Text>
                <Select
                    id="source-extensions" mode="multiple" value={value.extensions} disabled={!editing}
                    options={SOURCE_EXTENSIONS.map(ext => ({ value: ext, label: `.${ext}` }))}
                    placeholder="Choose at least one" style={{ width: "100%", marginTop: 6 }}
                    onChange={extensions => onChange({ ...value, extensions })}
                />
                <FieldDesc>Image types picked up by a sync.</FieldDesc>
            </Col>
            <Col xs={24} md={12}>
                <Text strong style={{ fontSize: 13 }}><label htmlFor="source-excludes">Exclude patterns</label></Text>
                <Select
                    id="source-excludes" mode="tags" value={value.exclude_globs} disabled={!editing} tokenSeparators={[","]}
                    placeholder="e.g. *_draft.*" style={{ width: "100%", marginTop: 6 }} open={false} suffixIcon={null}
                    onChange={exclude_globs => onChange({ ...value, exclude_globs })}
                />
                <FieldDesc>
                    Glob patterns matched on the file name. Files named like a publish derivative are always excluded.
                </FieldDesc>
            </Col>
        </Row>
    );
}
