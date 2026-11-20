import { useCallback, useEffect, useRef, useState } from "react";
import { App } from "antd";
import { getErrorMessage } from "../../../api/client";
import { fetchGroupImages, fetchImages } from "../../../api/images";
import type { ImageListQuery, ImagePage, ImageRecord } from "../../../types/image";
import { appendToGroup, mapImages } from "../imageUtils";

/**
 * Loads one page of image groups. `version` increments on every successful fetch so
 * dependants (e.g. the selection) can reset when fresh data arrives. Only the latest
 * request is applied, so a slow earlier response cannot overwrite a newer one. `error` is
 * the message of the last failed load, cleared by the next successful one.
 *
 * A group arrives with its first images only; `loadMore` appends the next slice. Reloading the
 * page starts every group from its first slice again.
 */
export function useImageList({ page, status, search, sortBy, sortOrder }: ImageListQuery) {
    const { message } = App.useApp();
    const [data, setData] = useState<ImagePage | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [version, setVersion] = useState(0);
    const latestRequest = useRef(0);
    /** Groups (by `group ?? ""`) whose next slice is being fetched. */
    const [loadingMore, setLoadingMore] = useState<ReadonlySet<string>>(new Set());

    const reload = useCallback(async () => {
        const request = ++latestRequest.current;
        setLoading(true);
        try {
            const result = await fetchImages({ page, status, search, sortBy, sortOrder });
            if (request !== latestRequest.current) return;
            setData(result);
            setError(null);
            setVersion(v => v + 1);
        } catch (e) {
            if (request !== latestRequest.current) return;
            const text = getErrorMessage(e, "Failed to load images");
            setError(text);
            message.error(text);
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
    }, [page, status, search, sortBy, sortOrder, message]);

    useEffect(() => { void reload(); }, [reload]);

    const updateImages = useCallback((update: (image: ImageRecord) => ImageRecord) => {
        setData(prev => (prev ? mapImages(prev, update) : prev));
    }, []);

    const loadMore = useCallback(async (group: string | null, offset: number) => {
        const id = group ?? "";
        const request = latestRequest.current;
        setLoadingMore(prev => new Set(prev).add(id));
        try {
            const more = await fetchGroupImages(group, offset, { status, search, sortBy, sortOrder });
            // Dropped if the page was reloaded meanwhile: the slice belongs to the old list.
            if (request === latestRequest.current) setData(prev => (prev ? appendToGroup(prev, more) : prev));
        } catch (e) {
            message.error(getErrorMessage(e, "Failed to load more images"));
        } finally {
            setLoadingMore(prev => {
                const next = new Set(prev);
                next.delete(id);
                return next;
            });
        }
    }, [status, search, sortBy, sortOrder, message]);

    return { data, loading, error, version, reload, updateImages, loadMore, loadingMore };
}
