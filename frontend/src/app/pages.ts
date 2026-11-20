import { lazy } from "react";

// Route-level code splitting: each page is its own chunk.
export const LoginPage = lazy(() => import("../features/login/LoginPage"));
export const DashboardPage = lazy(() => import("../features/dashboard/DashboardPage"));
export const ImagesPage = lazy(() => import("../features/images/ImagesPage"));
export const ReviewPage = lazy(() => import("../features/review/ReviewPage"));
export const ImportPage = lazy(() => import("../features/imports/ImportPage"));
export const JobsPage = lazy(() => import("../features/jobs/JobsPage"));
export const PresetsPage = lazy(() => import("../features/presets/PresetsPage"));
export const PlaygroundPage = lazy(() => import("../features/playground/PlaygroundPage"));
export const FailedPage = lazy(() => import("../features/failed/FailedPage"));
export const ActivityPage = lazy(() => import("../features/activity/ActivityPage"));
export const UsersPage = lazy(() => import("../features/users/UsersPage"));
export const SettingsPage = lazy(() => import("../features/settings/SettingsPage"));
