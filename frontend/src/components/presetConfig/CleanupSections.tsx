import { useId } from "react";
import { InputNumber, Select, Switch } from "antd";
import { PRESET_LIMITS, REMBG_MODEL_OPTIONS, UPSCALE_METHOD_OPTIONS } from "../../constants/presetOptions";
import { ConfigSection } from "./ConfigSection";
import { Field, FieldGrid, InlineSwitchField } from "../Field";
import type { SectionProps } from "./types";

const FULL = { width: "100%" } as const;

export function ContrastSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { contrast } = config;
    return (
        <ConfigSection
            title="Contrast" description="Boost contrast before anything else; helps with flat, washed-out photos."
            enabled={contrast.enabled} onToggle={enabled => update("contrast", { enabled })} disabled={disabled} issues={issues}
        >
            <FieldGrid>
                <Field htmlFor={id} label="Factor" help="1.0 = unchanged, 1.1 = subtle boost.">
                    <InputNumber id={id} {...PRESET_LIMITS.contrastFactor} value={contrast.factor} disabled={disabled} style={FULL}
                                 onChange={factor => factor !== null && update("contrast", { factor })} />
                </Field>
            </FieldGrid>
        </ConfigSection>
    );
}

export function BackgroundSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { background } = config;
    const set = (patch: Partial<typeof background>) => update("background", patch);
    return (
        <ConfigSection
            title="Background" description="Cut the subject out with a local segmentation model."
            enabled={background.remove} onToggle={remove => set({ remove })} disabled={disabled} issues={issues}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-model`} label="Model" help="Downloaded on first use.">
                    <Select id={`${id}-model`} options={REMBG_MODEL_OPTIONS} value={background.model} disabled={disabled}
                            onChange={model => set({ model })} style={FULL} />
                </Field>
            </FieldGrid>
            <InlineSwitchField
                label="Skip plain backgrounds"
                help="Keep the image as is when its corners are already near-white."
                control={<Switch checked={background.skip_if_plain} disabled={disabled} aria-label="Skip plain backgrounds"
                                 onChange={skip_if_plain => set({ skip_if_plain })} />}
            />
            {background.skip_if_plain && (
                <FieldGrid>
                    <Field htmlFor={`${id}-plain`} label="Plain threshold" help="Corner brightness (0–255) that counts as plain.">
                        <InputNumber id={`${id}-plain`} {...PRESET_LIMITS.threshold} value={background.plain_threshold} disabled={disabled}
                                     style={FULL} onChange={value => value !== null && set({ plain_threshold: value })} />
                    </Field>
                </FieldGrid>
            )}
            <InlineSwitchField
                label="Alpha matting"
                help="Refines soft edges such as hair or fur. Slower."
                control={<Switch checked={background.alpha_matting} disabled={disabled} aria-label="Alpha matting"
                                 onChange={alpha_matting => set({ alpha_matting })} />}
            />
            {background.alpha_matting && (
                <FieldGrid>
                    <Field htmlFor={`${id}-fg`} label="Foreground threshold" help="0–255">
                        <InputNumber id={`${id}-fg`} {...PRESET_LIMITS.threshold} value={background.fg_threshold} disabled={disabled}
                                     style={FULL} onChange={value => value !== null && set({ fg_threshold: value })} />
                    </Field>
                    <Field htmlFor={`${id}-bg`} label="Background threshold" help="0–255">
                        <InputNumber id={`${id}-bg`} {...PRESET_LIMITS.threshold} value={background.bg_threshold} disabled={disabled}
                                     style={FULL} onChange={value => value !== null && set({ bg_threshold: value })} />
                    </Field>
                    <Field htmlFor={`${id}-erode`} label="Erode size (px)" help="Shrinks the mask to remove fringes.">
                        <InputNumber id={`${id}-erode`} {...PRESET_LIMITS.erodeSize} value={background.erode_size} disabled={disabled}
                                     style={FULL} onChange={value => value !== null && set({ erode_size: value })} />
                    </Field>
                </FieldGrid>
            )}
        </ConfigSection>
    );
}

export function AutocropSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { autocrop } = config;
    return (
        <ConfigSection
            title="Autocrop" description="Trim empty or transparent borders around the subject."
            enabled={autocrop.enabled} onToggle={enabled => update("autocrop", { enabled })} disabled={disabled} issues={issues}
        >
            <FieldGrid>
                <Field htmlFor={id} label="Padding (px)" help="Space kept around the subject (0–200).">
                    <InputNumber id={id} {...PRESET_LIMITS.padding} value={autocrop.padding} disabled={disabled} style={FULL}
                                 onChange={padding => padding !== null && update("autocrop", { padding })} />
                </Field>
            </FieldGrid>
        </ConfigSection>
    );
}

export function UpscaleSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { upscale } = config;
    return (
        <ConfigSection
            title="Upscale" description="Double the resolution of small images before placing them."
            enabled={upscale.enabled} onToggle={enabled => update("upscale", { enabled })} disabled={disabled} issues={issues}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-below`} label="When longest side is below (px)">
                    <InputNumber id={`${id}-below`} {...PRESET_LIMITS.upscaleBelow} value={upscale.below_px} disabled={disabled}
                                 style={FULL} onChange={below_px => below_px !== null && update("upscale", { below_px })} />
                </Field>
                <Field htmlFor={`${id}-method`} label="Method">
                    <Select id={`${id}-method`} options={UPSCALE_METHOD_OPTIONS} value={upscale.method} disabled={disabled}
                            style={FULL} onChange={method => update("upscale", { method })} />
                </Field>
            </FieldGrid>
        </ConfigSection>
    );
}
