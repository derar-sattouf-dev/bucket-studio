import { useCallback, useEffect, useRef, useState } from "react";

/**
 * An object URL owned by the component: `setBlob` replaces it (revoking the previous one)
 * and the last one is revoked on unmount, so in-memory images never leak.
 */
export function useObjectUrl(): [string | null, (blob: Blob | null) => void] {
    const [url, setUrl] = useState<string | null>(null);
    const urlRef = useRef<string | null>(null);

    const setBlob = useCallback((blob: Blob | null) => {
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
        urlRef.current = blob ? URL.createObjectURL(blob) : null;
        setUrl(urlRef.current);
    }, []);

    useEffect(() => () => {
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    }, []);

    return [url, setBlob];
}
