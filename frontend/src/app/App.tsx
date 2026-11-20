import { Suspense } from "react";
import { App as AntApp, ConfigProvider, Layout } from "antd";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthProvider";
import { RequireAdmin } from "../auth/RequireAdmin";
import { RequireAuth } from "../auth/RequireAuth";
import { PageLoader } from "../components/PageLoader";
import { AppLayout } from "./AppLayout";
import {
    ActivityPage, DashboardPage, FailedPage, ImagesPage, ImportPage, JobsPage, LoginPage,
    PlaygroundPage, PresetsPage, ReviewPage, SettingsPage, UsersPage,
} from "./pages";
import { theme } from "./theme";
import { useDocumentTitle } from "./useDocumentTitle";

function AppRoutes() {
    useDocumentTitle();
    return (
        <Routes>
            <Route
                path="/login"
                element={
                    <Layout style={{ minHeight: "100vh" }}>
                        <Suspense fallback={<PageLoader />}><LoginPage /></Suspense>
                    </Layout>
                }
            />
            <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/images" element={<ImagesPage />} />
                <Route path="/review" element={<ReviewPage />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/jobs" element={<JobsPage />} />
                <Route path="/presets" element={<PresetsPage />} />
                <Route path="/playground" element={<PlaygroundPage />} />
                <Route path="/failed" element={<FailedPage />} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route path="/users" element={<RequireAdmin><UsersPage /></RequireAdmin>} />
                <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

export function App() {
    return (
        <ConfigProvider theme={theme}>
            {/* component={false}: provides themed message/modal APIs without an extra wrapper element */}
            <AntApp component={false}>
                <AuthProvider>
                    <AppRoutes />
                </AuthProvider>
            </AntApp>
        </ConfigProvider>
    );
}
