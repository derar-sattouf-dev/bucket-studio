import { useId } from "react";
import { Alert, Input, InputNumber, Select, Switch } from "antd";
import { AI_ENGINE_OPTIONS, AI_SIZE_OPTIONS, OUTPUT_FORMAT_OPTIONS, PRESET_LIMITS } from "../../constants/presetOptions";
import { producesTransparency } from "../../utils/presetConfig";
import { ConfigSection } from "./ConfigSection";
import { Field, FieldGrid, InlineSwitchField } from "../Field";
import type { SectionProps } from "./types";

const FULL = { width: "100%" } as const;
const KB = 1024;
const DEFAULT_LIMIT_KB = 500;

export function OutputSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { output } = config;
    const set = (patch: Partial<typeof output>) => update("output", patch);
    const transparent = producesTransparency(config);
    const limited = output.max_bytes !== null;

    return (
        <ConfigSection
            title="Output" description="Encoding of the final image. Always applied."
            disabled={disabled} issues={issues}
            note={transparent && (
                <Alert
                    type="info" showIcon
                    title="This preset produces transparency"
                    description={'Use PNG or WebP. "Keep original format" only works for PNG and WebP sources; JPEG cannot store transparency.'}
                />
            )}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-format`} label="Format"
                       help="Publishing needs the source's format: use “Keep original format” for presets you will publish.">
                    <Select id={`${id}-format`} options={OUTPUT_FORMAT_OPTIONS} value={output.format} disabled={disabled}
                            style={FULL} onChange={format => set({ format })} />
                </Field>
                <Field htmlFor={`${id}-quality`} label="Quality" help="1–95, ignored for PNG.">
                    <InputNumber id={`${id}-quality`} {...PRESET_LIMITS.quality} value={output.quality}
                                 disabled={disabled || output.format === "png"} style={FULL}
                                 onChange={quality => quality !== null && set({ quality })} />
                </Field>
            </FieldGrid>
            <InlineSwitchField
                label="Limit file size"
                help="Lowers quality, then dimensions, until the file fits."
                control={<Switch checked={limited} disabled={disabled} aria-label="Limit file size"
                                 onChange={on => set({ max_bytes: on ? DEFAULT_LIMIT_KB * KB : null })} />}
            />
            {limited && (
                <FieldGrid>
                    <Field htmlFor={`${id}-max`} label="Maximum size (KB)" help="At least 10 KB.">
                        <InputNumber id={`${id}-max`} min={PRESET_LIMITS.minMaxBytes / KB} max={PRESET_LIMITS.maxMaxBytes / KB} precision={0}
                                     value={output.max_bytes === null ? null : Math.round(output.max_bytes / KB)}
                                     disabled={disabled} style={FULL}
                                     onChange={value => value !== null && set({ max_bytes: value * KB })} />
                    </Field>
                </FieldGrid>
            )}
        </ConfigSection>
    );
}

export function AiSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { ai } = config;
    const set = (patch: Partial<typeof ai>) => update("ai", patch);
    const enabled = ai.engine !== "none";

    return (
        <ConfigSection
            title="AI regeneration"
            description="Regenerate images with an AI model instead of local background removal."
            enabled={enabled} onToggle={on => set({ engine: on ? "openai" : "none" })} disabled={disabled} issues={issues}
            note={<Alert type="warning" showIcon title="Images are sent to a third-party API, which is billed per image." />}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-engine`} label="Model provider" help="Needs the matching API key on the server.">
                    <Select id={`${id}-engine`} options={AI_ENGINE_OPTIONS} value={enabled ? ai.engine : undefined}
                            disabled={disabled} style={FULL} onChange={engine => set({ engine })} />
                </Field>
                <Field htmlFor={`${id}-below`} label="Only when longest side is below (px)" help="0 = every image.">
                    <InputNumber id={`${id}-below`} {...PRESET_LIMITS.aiBelow} value={ai.below_px} disabled={disabled}
                                 style={FULL} onChange={below_px => below_px !== null && set({ below_px })} />
                </Field>
                {ai.engine === "openai" && (
                    <Field htmlFor={`${id}-size`} label="Output size">
                        <Select id={`${id}-size`} options={AI_SIZE_OPTIONS} value={ai.size} disabled={disabled}
                                style={FULL} onChange={size => set({ size })} />
                    </Field>
                )}
            </FieldGrid>
            <Field htmlFor={`${id}-prompt`} label="Prompt" help="Leave empty to use the built-in prompt.">
                <Input.TextArea
                    id={`${id}-prompt`} rows={4} maxLength={PRESET_LIMITS.promptLength} showCount disabled={disabled}
                    value={ai.prompt ?? ""} placeholder="e.g. Isolate the subject on a clean white background…"
                    onChange={event => set({ prompt: event.target.value || null })}
                />
            </Field>
        </ConfigSection>
    );
}
