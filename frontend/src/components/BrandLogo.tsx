import { LOGO_URL } from "../constants/app";

/** The brand mark. Decorative: the app name is always shown next to it. */
export function BrandLogo({ size = 28 }: { size?: number }) {
    return <img src={LOGO_URL} alt="" width={size} height={size} style={{ display: "block", borderRadius: size / 4 }} />;
}
