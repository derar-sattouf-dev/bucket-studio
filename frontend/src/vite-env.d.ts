/// <reference types="vite/client" />

interface ImportMetaEnv {
    /**
     * Optional override for the API base URL (build-time, public). Leave unset: the API is
     * served same-origin under `/api` (nginx when deployed, the Vite proxy in development).
     */
    readonly VITE_API_URL?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
