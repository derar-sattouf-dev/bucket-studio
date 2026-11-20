import type { PresetConfig } from "../../types/preset";

export type UpdateSection = <Section extends keyof PresetConfig>(
    section: Section,
    patch: Partial<PresetConfig[Section]>,
) => void;

/** Props shared by every section of the preset editor. */
export interface SectionProps {
    config: PresetConfig;
    update: UpdateSection;
    disabled?: boolean;
    issues: string[];
}
