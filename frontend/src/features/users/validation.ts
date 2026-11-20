import type { Rule } from "antd/es/form";

// Mirrors the backend: usernames ^[A-Za-z0-9_.-]{3,64}$, passwords 8–72 bytes (bcrypt limit).
export const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,64}$/;
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_BYTES = 72;

export const usernameRules: Rule[] = [
    { required: true, message: "Enter a username" },
    { pattern: USERNAME_PATTERN, message: "3–64 characters: letters, digits, \"_\", \".\" or \"-\"" },
];

export const passwordRules: Rule[] = [
    { required: true, message: "Enter a password" },
    { min: PASSWORD_MIN_LENGTH, message: `At least ${PASSWORD_MIN_LENGTH} characters` },
    {
        validator: (_, value: string | undefined) =>
            !value || new TextEncoder().encode(value).length <= PASSWORD_MAX_BYTES
                ? Promise.resolve()
                : Promise.reject(new Error(`At most ${PASSWORD_MAX_BYTES} bytes`)),
    },
];
