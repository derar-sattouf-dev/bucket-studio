import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { fetchCurrentUser, login as loginRequest } from "../api/auth";
import { isAbortError } from "../api/client";
import type { CurrentUser } from "../types/user";
import { AuthContext, type AuthContextValue } from "./AuthContext";
import { clearToken, getToken, setToken, subscribeToToken } from "./tokenStorage";

/** Profile fetched for a specific token, so a stale profile is never shown for a new session. */
interface LoadedUser {
    token: string;
    user: CurrentUser | null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const token = useSyncExternalStore(subscribeToToken, getToken);
    const [loaded, setLoaded] = useState<LoadedUser | null>(null);

    useEffect(() => {
        if (!token) return;
        const controller = new AbortController();
        fetchCurrentUser(controller.signal)
            .then(user => setLoaded({ token, user }))
            .catch((error: unknown) => {
                // A 401 already cleared the token; anything else leaves the user signed in
                // but without admin rights in the UI (the server enforces roles anyway).
                if (!isAbortError(error)) setLoaded({ token, user: null });
            });
        return () => controller.abort();
    }, [token]);

    const login = useCallback(async (username: string, password: string) => {
        const { token: newToken, expires_in } = await loginRequest(username, password);
        setToken(newToken, expires_in);
    }, []);

    const logout = useCallback(() => clearToken(), []);

    const value = useMemo<AuthContextValue>(() => {
        const currentUser = token && loaded?.token === token ? loaded.user : null;
        return {
            isAuthenticated: token !== null,
            currentUser,
            isAdmin: currentUser?.is_admin ?? false,
            isLoadingUser: token !== null && loaded?.token !== token,
            login,
            logout,
        };
    }, [token, loaded, login, logout]);

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
