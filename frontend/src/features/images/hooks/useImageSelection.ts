import { useCallback, useMemo, useState } from "react";
import type { ImageGroup } from "../../../types/image";
import { isPublishable, keysOf } from "../imageUtils";

const EMPTY = new Set<string>();

interface SelectionState {
    version: number;
    keys: Set<string>;
}

/**
 * Image selection across the groups of one page (by source key). It resets whenever a new
 * page of data (`version`) is loaded, so it never points at images that are no longer shown.
 */
export function useImageSelection(groups: ImageGroup[], version: number) {
    const [state, setState] = useState<SelectionState>({ version, keys: EMPTY });
    const selected = state.version === version ? state.keys : EMPTY;

    const allImages = useMemo(() => groups.flatMap(group => group.images), [groups]);

    /** Within `scope`, makes exactly `chosen` selected; keys outside `scope` are untouched. */
    const replaceWithin = useCallback((scope: string[], chosen: string[]) => {
        setState(prev => {
            const next = new Set(prev.version === version ? prev.keys : EMPTY);
            scope.forEach(key => next.delete(key));
            chosen.forEach(key => next.add(key));
            return { version, keys: next };
        });
    }, [version]);

    const allSelected = allImages.length > 0 && allImages.every(image => selected.has(image.source_key));

    const toggleAll = useCallback(() => {
        const keys = keysOf(allImages);
        replaceWithin(keys, allSelected ? [] : keys);
    }, [allImages, allSelected, replaceWithin]);

    const clear = useCallback(() => setState({ version, keys: new Set() }), [version]);

    const keys = useMemo(() => {
        const images = allImages.filter(image => selected.has(image.source_key));
        return {
            all: keysOf(images),
            publishable: keysOf(images.filter(isPublishable)),
            published: keysOf(images.filter(image => image.is_published)),
        };
    }, [allImages, selected]);

    return { selected, allSelected, replaceWithin, toggleAll, clear, keys };
}

export type ImageSelection = ReturnType<typeof useImageSelection>;
