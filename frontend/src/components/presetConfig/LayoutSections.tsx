import { useId } from "react";
import { Alert, ColorPicker, InputNumber, Segmented, Slider } from "antd";
import { PRESET_LIMITS } from "../../constants/presetOptions";
import { DEFAULT_PRESET_CONFIG, TRANSPARENT, isResizeEnabled } from "../../utils/presetConfig";
import { ConfigSection } from "./ConfigSection";
import { Field, FieldGrid } from "../Field";
import type { SectionProps } from "./types";

const FULL = { width: "100%" } as const;
const DEFAULT_RESIZE_PX = 2000;

type BackgroundMode = "color" | "transparent";

export function CanvasSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { canvas } = config;
    const set = (patch: Partial<typeof canvas>) => update("canvas", patch);
    const mode: BackgroundMode = canvas.background === TRANSPARENT ? "transparent" : "color";
    const color = mode === "color" ? canvas.background : DEFAULT_PRESET_CONFIG.canvas.background;

    return (
        <ConfigSection
            title="Canvas" description="Center the subject on a fixed-size canvas, scaled to a share of it."
            enabled={canvas.enabled} onToggle={enabled => set({ enabled })} disabled={disabled} issues={issues}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-w`} label="Width (px)" help="16–8000">
                    <InputNumber id={`${id}-w`} {...PRESET_LIMITS.canvasSize} value={canvas.width} disabled={disabled} style={FULL}
                                 onChange={width => width !== null && set({ width })} />
                </Field>
                <Field htmlFor={`${id}-h`} label="Height (px)" help="16–8000">
                    <InputNumber id={`${id}-h`} {...PRESET_LIMITS.canvasSize} value={canvas.height} disabled={disabled} style={FULL}
                                 onChange={height => height !== null && set({ height })} />
                </Field>
            </FieldGrid>
            <Field htmlFor={`${id}-fill`} label={`Subject fills ${Math.round(canvas.fill_ratio * 100)}% of the canvas`}>
                <Slider id={`${id}-fill`} {...PRESET_LIMITS.fillRatio} value={canvas.fill_ratio} disabled={disabled}
                        tooltip={{ formatter: value => `${Math.round((value ?? 0) * 100)}%` }}
                        onChange={fill_ratio => set({ fill_ratio })} style={{ margin: "6px 8px" }} />
            </Field>
            <Field htmlFor={`${id}-bg`} label="Background">
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <Segmented<BackgroundMode>
                        id={`${id}-bg`}
                        value={mode}
                        disabled={disabled}
                        options={[{ value: "color", label: "Color" }, { value: "transparent", label: "Transparent" }]}
                        onChange={next => set({ background: next === "transparent" ? TRANSPARENT : color })}
                    />
                    {mode === "color" && (
                        <ColorPicker
                            value={color} disabled={disabled} disabledAlpha showText format="hex"
                            aria-label="Background color"
                            onChangeComplete={value => set({ background: value.toHexString().slice(0, 7).toUpperCase() })}
                        />
                    )}
                </div>
            </Field>
        </ConfigSection>
    );
}

export function ResizeSection({ config, update, disabled, issues }: SectionProps) {
    const id = useId();
    const { resize } = config;
    const enabled = isResizeEnabled(config);
    const toggle = (on: boolean) =>
        update("resize", on ? { max_width: DEFAULT_RESIZE_PX, max_height: DEFAULT_RESIZE_PX } : { max_width: null, max_height: null });

    return (
        <ConfigSection
            title="Resize" description="Shrink images to fit within a maximum size, keeping the aspect ratio."
            enabled={enabled} onToggle={toggle} disabled={disabled} issues={issues}
            note={config.canvas.enabled && (
                <Alert type="info" showIcon title="Ignored while Canvas is on: the canvas already sets the output size." />
            )}
        >
            <FieldGrid>
                <Field htmlFor={`${id}-w`} label="Max width (px)" help="Empty = no limit">
                    <InputNumber id={`${id}-w`} {...PRESET_LIMITS.resizeSize} value={resize.max_width} disabled={disabled}
                                 style={FULL} onChange={max_width => update("resize", { max_width })} />
                </Field>
                <Field htmlFor={`${id}-h`} label="Max height (px)" help="Empty = no limit">
                    <InputNumber id={`${id}-h`} {...PRESET_LIMITS.resizeSize} value={resize.max_height} disabled={disabled}
                                 style={FULL} onChange={max_height => update("resize", { max_height })} />
                </Field>
            </FieldGrid>
        </ConfigSection>
    );
}
