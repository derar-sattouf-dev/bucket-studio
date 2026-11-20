import type { ThemeConfig } from "antd";

/** System font stack: no web-font requests, so the CSP needs no third-party origins. */
export const FONT_FAMILY =
    'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif';

export const SIDEBAR_BG = "#0B3B37";

export const theme: ThemeConfig = {
    token: {
        colorPrimary: "#006A64",
        colorBgBase: "#FFFFFF",
        colorTextBase: "#161D1C",
        colorBorder: "#d1d5db",
        colorBgContainer: "#FFFFFF",
        colorBgLayout: "#f8fafc",
        colorError: "#BA1A1A",
        colorInfo: "#1A76CA",
        colorSuccess: "#2E837D",
        fontFamily: FONT_FAMILY,
        borderRadius: 8,
        borderRadiusLG: 12,
        borderRadiusSM: 6,
        boxShadow: "none",
        boxShadowSecondary: "none",
    },
    components: {
        Card: {
            colorBgContainer: "#FFFFFF",
            colorBorderSecondary: "#e2e8f0",
            borderRadiusLG: 12,
            boxShadowTertiary: "none",
        },
        Button: {
            borderRadius: 8,
            boxShadow: "none",
            primaryShadow: "none",
            defaultShadow: "none",
            dangerShadow: "none",
            fontWeight: 500,
        },
        Input: { borderRadius: 8 },
        Select: { borderRadius: 8 },
        Tag: { borderRadius: 6 },
        Modal: { borderRadiusLG: 12 },
        Drawer: { borderRadiusLG: 12 },
        Menu: { darkItemBg: SIDEBAR_BG, darkSubMenuItemBg: "#082F2C", darkItemSelectedBg: "#006A64" },
        Table: { borderRadius: 10, headerBorderRadius: 10 },
    },
};
