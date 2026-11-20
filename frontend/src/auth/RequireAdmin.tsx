import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { PageLoader } from "../components/PageLoader";
import { useAuth } from "./useAuth";

/** Route guard for admin-only pages. The server enforces the role too; this only hides UI. */
export function RequireAdmin({ children }: { children: ReactNode }) {
    const { isAdmin, isLoadingUser } = useAuth();
    if (isLoadingUser) return <PageLoader />;
    if (!isAdmin) return <Navigate to="/dashboard" replace />;
    return <>{children}</>;
}
