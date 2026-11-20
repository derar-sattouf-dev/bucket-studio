import { Button, Input, InputNumber, Select, Typography } from "antd";
import { ArrowRightOutlined, DeleteOutlined } from "@ant-design/icons";
import type { Derivative, DerivativeFit, DerivativeFormat } from "../../../types/settings";
import { renderDerivativeKey, withFormatEnding } from "../derivatives";

const { Text } = Typography;

const FIT_OPTIONS: { value: DerivativeFit; label: string }[] = [
    { value: "contain", label: "Contain (fit inside)" },
    { value: "cover", label: "Cover (crop to fill)" },
];

const FORMAT_OPTIONS: { value: DerivativeFormat; label: string }[] = [
    { value: "same", label: "Same as image" },
    { value: "jpeg", label: "JPEG" },
    { value: "png", label: "PNG" },
    { value: "webp", label: "WebP" },
];

/** Width/height range of a derivative, mirroring the server (`DerivativeSpec`). */
const DERIVATIVE_SIZE = { min: 16, max: 4000 } as const;

interface DerivativeRowProps {
    index: number;
    value: Derivative;
    exampleKey: string;
    error: string | null;
    editing: boolean;
    onChange: (patch: Partial<Derivative>) => void;
    onRemove: () => void;
}

/** One derivative: name template, size, fit, format and quality, with a live name preview. */
export function DerivativeRow({ index, value, exampleKey, error, editing, onChange, onRemove }: DerivativeRowProps) {
    const id = `derivative-${index}`;
    const label = (field: string, text: string) => (
        <label htmlFor={`${id}-${field}`} style={{ display: "block", fontSize: 11, color: "#64748b", marginBottom: 2 }}>{text}</label>
    );

    return (
        <div style={{ border: `1px solid ${error ? "#ffccc7" : "#e2e8f0"}`, borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "2fr repeat(2, 0.8fr) 1.3fr 1.1fr 0.7fr auto", gap: 8, alignItems: "end" }}>
                <div>
                    {label("name", "Name template")}
                    <Input id={`${id}-name`} value={value.name} disabled={!editing} status={error ? "error" : undefined}
                           onChange={e => onChange({ name: e.target.value })} placeholder="{stem}_thumb.{ext}" />
                </div>
                <div>
                    {label("width", "Width")}
                    <InputNumber id={`${id}-width`} {...DERIVATIVE_SIZE} value={value.width} disabled={!editing} placeholder="auto"
                                 style={{ width: "100%" }} onChange={width => onChange({ width })} />
                </div>
                <div>
                    {label("height", "Height")}
                    <InputNumber id={`${id}-height`} {...DERIVATIVE_SIZE} value={value.height} disabled={!editing} placeholder="auto"
                                 style={{ width: "100%" }} onChange={height => onChange({ height })} />
                </div>
                <div>
                    {label("fit", "Fit")}
                    <Select id={`${id}-fit`} options={FIT_OPTIONS} value={value.fit} disabled={!editing} style={{ width: "100%" }}
                            onChange={fit => onChange({ fit })} />
                </div>
                <div>
                    {label("format", "Format")}
                    <Select id={`${id}-format`} options={FORMAT_OPTIONS} value={value.format} disabled={!editing} style={{ width: "100%" }}
                            onChange={format => onChange({ format, name: withFormatEnding(value.name, format) })} />
                </div>
                <div>
                    {label("quality", "Quality")}
                    <InputNumber id={`${id}-quality`} min={1} max={95} value={value.quality} disabled={!editing} style={{ width: "100%" }}
                                 onChange={quality => quality !== null && onChange({ quality })} />
                </div>
                <Button danger type="text" icon={<DeleteOutlined />} disabled={!editing} onClick={onRemove}
                        aria-label={`Remove derivative ${value.name || index + 1}`} />
            </div>
            <div style={{ marginTop: 6, fontSize: 12 }}>
                {error ? <Text type="danger">{error}</Text> : (
                    <Text type="secondary">
                        <Text code style={{ fontSize: 11 }}>{exampleKey}</Text> <ArrowRightOutlined />{" "}
                        <Text code style={{ fontSize: 11 }}>{renderDerivativeKey(value.name, exampleKey)}</Text>
                    </Text>
                )}
            </div>
        </div>
    );
}
