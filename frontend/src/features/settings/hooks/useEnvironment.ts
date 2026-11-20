import { useEffect, useState } from "react";
import { getErrorMessage } from "../../../api/client";
import { fetchEnvironment } from "../../../api/settings";
import type { EnvironmentInfo } from "../../../types/settings";

/** Deployment facts from `.env`; they only change on restart, so they are loaded once. */
export function useEnvironment() {
    const [environment, setEnvironment] = useState<EnvironmentInfo | null>(null);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => {
        fetchEnvironment().then(setEnvironment).catch(e => setError(getErrorMessage(e, "Failed to load environment info")));
    }, []);
    return { environment, error };
}
