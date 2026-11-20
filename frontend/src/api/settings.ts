import type { AdminSettings, EnvironmentInfo, RuntimeSettings, Settings } from "../types/settings";
import { apiFetch, apiJson } from "./client";

/** Readable by every signed-in user. */
export function fetchSettings(): Promise<Settings> {
    return apiJson<Settings>("/settings/");
}

/** Readable by every signed-in user: values that come from `.env` and need a restart. */
export function fetchEnvironment(): Promise<EnvironmentInfo> {
    return apiJson<EnvironmentInfo>("/settings/environment");
}

/** Admin only. */
export function saveRuntimeSettings(patch: Partial<RuntimeSettings>): Promise<Settings> {
    return apiJson<Settings>("/settings/", { method: "PATCH", json: patch });
}

/** Admin only. Resolves when the password is correct, throws otherwise. */
export async function verifyAdminPassword(adminPassword: string): Promise<void> {
    await apiFetch("/settings/verify-admin", { method: "POST", json: { admin_password: adminPassword } });
}

/** Admin only: prefixes, publish derivatives and source filters (step-up password required). */
export function saveAdminSettings(patch: Partial<AdminSettings>, adminPassword: string): Promise<Settings> {
    return apiJson<Settings>("/settings/admin", { method: "PATCH", json: { ...patch, admin_password: adminPassword } });
}

/** Admin only. `confirm` must be the literal "RESET". */
export async function resetDatabase(adminPassword: string): Promise<void> {
    await apiFetch("/settings/reset-db", { method: "POST", json: { admin_password: adminPassword, confirm: "RESET" } });
}
