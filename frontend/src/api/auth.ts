import type { CurrentUser, LoginResponse } from "../types/user";
import { apiJson } from "./client";

/** `auth: false` — a 401 here means bad credentials, not an expired session. */
export function login(username: string, password: string): Promise<LoginResponse> {
    return apiJson<LoginResponse>("/auth/login", { method: "POST", json: { username, password }, auth: false });
}

export function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
    return apiJson<CurrentUser>("/auth/me", { signal });
}
