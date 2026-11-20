import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { APP_NAME } from "../constants/app";

const PAGE_TITLES: Record<string, string> = {
    "/dashboard": "Dashboard",
    "/images": "Images",
    "/review": "Review",
    "/import": "Import",
    "/jobs": "Batch jobs",
    "/presets": "Presets",
    "/playground": "Playground",
    "/failed": "Failures",
    "/activity": "Activity",
    "/users": "Users",
    "/settings": "Settings",
    "/login": "Sign in",
};

export function useDocumentTitle(): void {
    const { pathname } = useLocation();
    useEffect(() => {
        const title = PAGE_TITLES[pathname];
        document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
    }, [pathname]);
}
