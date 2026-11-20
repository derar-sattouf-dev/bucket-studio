import { useEffect, useState } from "react";

export interface Dimensions {
    width: number;
    height: number;
}

interface Loaded {
    url: string;
    dimensions: Dimensions | null;
}

/** Natural size of the image at `url` (null while loading, on error, or without a URL). */
export function useImageDimensions(url: string | null): Dimensions | null {
    const [loaded, setLoaded] = useState<Loaded | null>(null);
    useEffect(() => {
        if (!url) return;
        const image = new Image();
        image.referrerPolicy = "no-referrer";
        image.onload = () => setLoaded({ url, dimensions: { width: image.naturalWidth, height: image.naturalHeight } });
        image.onerror = () => setLoaded({ url, dimensions: null });
        image.src = url;
        return () => {
            image.onload = null;
            image.onerror = null;
        };
    }, [url]);
    return url && loaded?.url === url ? loaded.dimensions : null;
}
