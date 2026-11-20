import { useCallback, useEffect, useRef, useState } from "react";
import { getErrorMessage } from "../api/client";
import type { PagedImages, PagedImagesQuery } from "../types/image";
import { useDebouncedValue } from "./useDebouncedValue";

const SEARCH_DEBOUNCE_MS = 300;

/**
 * A server-paginated, server-searched image list (review queue, failures). The search is
 * debounced and returns to page 1; only the latest request is applied, so a slow earlier
 * response cannot overwrite a newer one. `fetchPage` must be a stable function.
 */
export function usePagedImages(fetchPage: (query: PagedImagesQuery) => Promise<PagedImages>, pageSize: number, errorText: string) {
    const [searchInput, setSearchInput] = useState("");
    const search = useDebouncedValue(searchInput.trim(), SEARCH_DEBOUNCE_MS);
    // The page belongs to one search: a new search starts at page 1 without an extra request.
    const [position, setPosition] = useState({ page: 1, search: "" });
    const page = position.search === search ? position.page : 1;
    const setPage = useCallback((next: number) => setPosition({ page: next, search }), [search]);

    const [data, setData] = useState<PagedImages | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const latestRequest = useRef(0);

    const reload = useCallback(async () => {
        const request = ++latestRequest.current;
        setLoading(true);
        try {
            const result = await fetchPage({ page, pageSize, search });
            if (request !== latestRequest.current) return;
            setData(result);
            setError(null);
            // The page emptied (its images were published or retried): step back to the last one.
            if (result.items.length === 0 && page > result.total_pages) setPosition({ page: result.total_pages, search });
        } catch (e) {
            if (request !== latestRequest.current) return;
            setError(getErrorMessage(e, errorText));
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
    }, [fetchPage, page, pageSize, search, errorText]);

    useEffect(() => { void reload(); }, [reload]);

    return {
        items: data?.items ?? [],
        /** Images matching the current search, across all pages. */
        total: data?.total ?? 0,
        loaded: data !== null,
        loading, error, reload,
        page, pageSize, setPage,
        searchInput, setSearchInput,
        /** The (debounced) search the list currently shows; empty when unfiltered. */
        search,
    };
}
