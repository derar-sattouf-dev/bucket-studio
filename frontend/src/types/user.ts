export interface User {
    id: number;
    username: string;
    created_at: string;
    is_active: boolean;
    is_admin: boolean;
}

/** Response of `GET /auth/me`. */
export interface CurrentUser {
    username: string;
    is_admin: boolean;
}

export interface LoginResponse {
    token: string;
    /** Token lifetime in seconds. */
    expires_in: number;
}

export interface CreateUserPayload {
    username: string;
    password: string;
    is_admin: boolean;
    admin_password: string;
}
