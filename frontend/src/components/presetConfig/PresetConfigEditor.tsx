import { useMemo, type ComponentType } from "react";
import type { PresetConfig } from "../../types/preset";
import { validatePresetConfig } from "../../utils/presetConfig";
import { AutocropSection, BackgroundSection, ContrastSection, UpscaleSection } from "./CleanupSections";
import { CanvasSection, ResizeSection } from "./LayoutSections";
import { AiSection, OutputSection } from "./OutputSections";
import type { SectionProps, UpdateSection } from "./types";

interface PresetConfigEditorProps {
    value: PresetConfig;
    onChange: (next: PresetConfig) => void;
    /** Read-only view (non-admins). */
    disabled?: boolean;
}

const SECTIONS: { key: keyof PresetConfig; Component: ComponentType<SectionProps> }[] = [
    { key: "contrast", Component: ContrastSection },
    { key: "background", Component: BackgroundSection },
    { key: "autocrop", Component: AutocropSection },
    { key: "upscale", Component: UpscaleSection },
    { key: "canvas", Component: CanvasSection },
    { key: "resize", Component: ResizeSection },
    { key: "output", Component: OutputSection },
    { key: "ai", Component: AiSection },
];

/** Controlled editor for a {@link PresetConfig}; cross-field problems are shown in their section. */
export function PresetConfigEditor({ value, onChange, disabled }: PresetConfigEditorProps) {
    const issuesBySection = useMemo(() => {
        const grouped = new Map<keyof PresetConfig, string[]>();
        validatePresetConfig(value).forEach(({ section, message }) => {
            grouped.set(section, [...(grouped.get(section) ?? []), message]);
        });
        return grouped;
    }, [value]);

    const update: UpdateSection = (section, patch) => onChange({ ...value, [section]: { ...value[section], ...patch } });

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {SECTIONS.map(({ key, Component }) => (
                <Component key={key} config={value} update={update} disabled={disabled} issues={issuesBySection.get(key) ?? []} />
            ))}
        </div>
    );
}
