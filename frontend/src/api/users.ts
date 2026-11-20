import type { CreateUserPayload, User } from "../types/user";
import { apiFetch, apiJson } from "./client";

// Every /users endpoint is admin only.

export function fetchUsers(): Promise<User[]> {
    return apiJson<User[]>("/users/");
}

export function createUser(payload: CreateUserPayload): Promise<User> {
    return apiJson<User>("/users/", { method: "POST", json: payload });
}

/** Deactivating revokes the user's access at once; their existing session stops working. */
export function setUserActive(userId: number, isActive: boolean, adminPassword: string): Promise<User> {
    return apiJson<User>(`/users/${userId}`, {
        method: "PATCH",
        json: { is_active: isActive, admin_password: adminPassword },
    });
}

export async function deleteUser(userId: number, adminPassword: string): Promise<void> {
    await apiFetch(`/users/${userId}`, { method: "DELETE", json: { admin_password: adminPassword } });
}
