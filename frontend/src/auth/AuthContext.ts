import { createContext } from "react";
import type { CurrentUser } from "../types/user";

export interface AuthContextValue {
    isAuthenticated: boolean;
    /** Profile from `GET /auth/me`; `null` while loading or signed out. */
    currentUser: CurrentUser | null;
    isAdmin: boolean;
    /** True while the profile for the current token is being fetched. */
    isLoadingUser: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
