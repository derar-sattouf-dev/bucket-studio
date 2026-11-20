import { useState } from "react";
import { Button, Empty, Input, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { Derivative } from "../../../types/settings";
import { EXAMPLE_KEY, NEW_DERIVATIVE, validateDerivative } from "../derivatives";
import { DerivativeRow } from "./DerivativeRow";
import { FieldDesc } from "./FieldDesc";

const { Text } = Typography;

/** The derivatives limit is not in the contract; this keeps the editor (and publishing) reasonable. */
const MAX_DERIVATIVES = 10;

interface DerivativesEditorProps {
    value: Derivative[];
    /** Accepted source extensions, to catch names that would overwrite a source. */
    extensions: string[];
    editing: boolean;
    onChange: (value: Derivative[]) => void;
}

/** Files generated next to each image when it is published. */
export function DerivativesEditor({ value, extensions, editing, onChange }: DerivativesEditorProps) {
    const [exampleKey, setExampleKey] = useState(EXAMPLE_KEY);

    const patch = (index: number, change: Partial<Derivative>) =>
        onChange(value.map((derivative, i) => (i === index ? { ...derivative, ...change } : derivative)));

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <FieldDesc>
                Use <Text code style={{ fontSize: 11 }}>{"{stem}"}</Text> and <Text code style={{ fontSize: 11 }}>{"{ext}"}</Text> of
                the image name. Empty width or height keeps the aspect ratio.
            </FieldDesc>
            <div style={{ display: "flex", alignItems: "center", gap: 8, maxWidth: 480 }}>
                <label htmlFor="derivative-example" style={{ fontSize: 12, whiteSpace: "nowrap" }}>Preview for</label>
                <Input id="derivative-example" size="small" value={exampleKey} onChange={e => setExampleKey(e.target.value || EXAMPLE_KEY)} />
            </div>
            {value.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No derivatives: only the image itself is published." />}
            {value.map((derivative, index) => (
                <DerivativeRow
                    key={index}
                    index={index}
                    value={derivative}
                    exampleKey={exampleKey}
                    error={validateDerivative(derivative, value, extensions)}
                    editing={editing}
                    onChange={change => patch(index, change)}
                    onRemove={() => onChange(value.filter((_, i) => i !== index))}
                />
            ))}
            <div>
                <Button icon={<PlusOutlined />} disabled={!editing || value.length >= MAX_DERIVATIVES}
                        onClick={() => onChange([...value, { ...NEW_DERIVATIVE, name: `{stem}_${value.length + 1}.{ext}` }])}>
                    Add derivative
                </Button>
            </div>
        </div>
    );
}
