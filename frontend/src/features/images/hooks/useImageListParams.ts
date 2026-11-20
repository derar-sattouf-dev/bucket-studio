import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { ImageListQuery } from "../../../types/image";

/** Image list filters, kept in the URL so views are linkable from the sidebar. */
export function useImageListParams() {
    const [searchParams, setSearchParams] = useSearchParams();

    const query: ImageListQuery = {
        page: parseInt(searchParams.get("page") ?? "1", 10),
        status: searchParams.get("status") ?? "",
        search: searchParams.get("search") ?? "",
        sortBy: searchParams.get("sort_by") ?? "updated_at",
        sortOrder: searchParams.get("sort_order") ?? "desc",
    };

    /** Empty values remove the param; changing a filter returns to page 1 unless `resetPage` is false. */
    const setParams = useCallback((patch: Record<string, string>, resetPage = true) => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            Object.entries(patch).forEach(([key, value]) => {
                if (value) next.set(key, value);
                else next.delete(key);
            });
            if (resetPage) next.set("page", "1");
            return next;
        }, { replace: true });
    }, [setSearchParams]);

    return { query, setParams };
}
