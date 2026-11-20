import type { Derivative, DerivativeFormat } from "../../types/settings";

/** Example used for the live preview of derivative names. */
export const EXAMPLE_KEY = "photos/2024/beach.jpg";

export const NEW_DERIVATIVE: Derivative = {
    name: "{stem}_thumb.{ext}", width: 300, height: 300, fit: "contain", format: "same", quality: 85,
};

/** Source extensions the server accepts in `source_filters.extensions`. */
export const SOURCE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"] as const;

const PLACEHOLDER = /\{([^}]*)\}/g;
const KNOWN_VARIABLES = new Set(["stem", "ext"]);
const ALLOWED_LITERALS = /^[A-Za-z0-9._-]*$/;

/** File endings a derivative name may use for each format. */
const FORMAT_ENDINGS: Record<DerivativeFormat, string[]> = {
    same: [".{ext}"],
    jpeg: [".jpg", ".jpeg"],
    png: [".png"],
    webp: [".webp"],
};

/** Swaps the ending of a name template to match `format` (keeps it when it already matches). */
export function withFormatEnding(name: string, format: DerivativeFormat): string {
    const endings = FORMAT_ENDINGS[format];
    if (endings.some(ending => name.endsWith(ending))) return name;
    const dot = name.lastIndexOf(".");
    return `${dot > 0 ? name.slice(0, dot) : name}${endings[0]}`;
}

function splitName(key: string): { folder: string; stem: string; ext: string } {
    const slash = key.lastIndexOf("/");
    const folder = key.slice(0, slash + 1);
    const file = key.slice(slash + 1);
    const dot = file.lastIndexOf(".");
    return dot > 0 ? { folder, stem: file.slice(0, dot), ext: file.slice(dot + 1) } : { folder, stem: file, ext: "" };
}

/** Full key of the derivative generated next to `sourceKey`. */
export function renderDerivativeKey(template: string, sourceKey: string): string {
    const { folder, stem, ext } = splitName(sourceKey);
    return folder + template.replaceAll("{stem}", stem).replaceAll("{ext}", ext);
}

/**
 * Same rules as the server: contains {stem}; otherwise only {ext} and [A-Za-z0-9._-]; no "..";
 * ends with ".{ext}" (format "same") or the format's extension; unique; and never equal to the
 * source file name for any accepted source extension.
 */
export function validateDerivative(derivative: Derivative, all: Derivative[], extensions: string[]): string | null {
    const { name, format } = derivative;
    if (!name.trim()) return "Name is required.";
    const unknown = [...name.matchAll(PLACEHOLDER)].map(match => match[1]).find(variable => !KNOWN_VARIABLES.has(variable));
    if (unknown !== undefined) return `Unknown variable {${unknown}}: use {stem} or {ext}.`;
    if (!name.includes("{stem}")) return "Name must contain {stem}.";
    if (!ALLOWED_LITERALS.test(name.replace(PLACEHOLDER, "")) || name.includes("..")) {
        return 'Use only letters, digits, ".", "_", "-" besides {stem} and {ext} (no "/" or "..").';
    }
    const endings = FORMAT_ENDINGS[format];
    if (!endings.some(ending => name.endsWith(ending))) return `With this format the name must end in ${endings.join(" or ")}.`;
    if (all.filter(other => other.name === name).length > 1) return "Two derivatives have the same name.";
    const clash = extensions.find(ext => renderDerivativeKey(name, `x.${ext}`) === `x.${ext}`);
    if (clash) return `Would overwrite .${clash} sources: the name must differ from the source file name.`;
    return null;
}
