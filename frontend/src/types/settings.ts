export interface RuntimeSettings {
    sync_interval_minutes: number;
    auto_process_after_sync: boolean;
    process_concurrency: number;
    ai_concurrency: number;
    max_retry_count: number;
    /** 0 = no grouping, 1 = first folder after the source prefix, 2 = first two folders, … */
    group_depth: number;
    default_preset_id: number;
    /** Largest accepted upload (Playground), in MB. */
    max_upload_mb: number;
    /** Largest image fetched from a URL (imports, Playground), in MB. */
    max_remote_fetch_mb: number;
    /** Larger images are rejected as possible decompression bombs. */
    max_image_megapixels: number;
    openai_image_model: string;
    gemini_image_model: string;
}

export type DerivativeFit = "contain" | "cover";
export type DerivativeFormat = "same" | "jpeg" | "png" | "webp";

/** A file generated next to a published image. `null` width/height keeps that dimension. */
export interface Derivative {
    /** Template with `{stem}` and `{ext}` of the source key, e.g. `{stem}_thumb.{ext}`. */
    name: string;
    width: number | null;
    height: number | null;
    fit: DerivativeFit;
    format: DerivativeFormat;
    quality: number;
}

export interface PublishConfig {
    derivatives: Derivative[];
}

export interface SourceFilters {
    /** Lowercase, without the dot. */
    extensions: string[];
    /** fnmatch patterns on the file name. */
    exclude_globs: string[];
}

export interface BucketPrefixes {
    source_prefix: string;
    output_prefix: string;
    backup_prefix: string;
}

/** Canned ACL applied to written objects; "" sends none (bucket policy decides). */
export type ObjectAcl =
    | ""
    | "private"
    | "public-read"
    | "authenticated-read"
    | "bucket-owner-read"
    | "bucket-owner-full-control";

/** Settings changed through `PATCH /settings/admin` (admin role + admin password). */
export interface AdminSettings extends BucketPrefixes {
    publish: PublishConfig;
    source_filters: SourceFilters;
    s3_object_acl: ObjectAcl;
    /** Lifetime of presigned image links. */
    presign_expires_seconds: number;
    /** Lifetime of a sign-in session. */
    session_minutes: number;
    login_max_attempts: number;
    login_lockout_minutes: number;
}

/** Read-only deployment facts from `GET /settings/environment` (set in `.env`). */
export interface EnvironmentInfo {
    app_name: string;
    s3_bucket: string;
    s3_endpoint_host: string;
    s3_public_endpoint_host: string | null;
    openai_configured: boolean;
    gemini_configured: boolean;
    api_docs_enabled: boolean;
    models_dir_writable: boolean;
    version: string;
}

export type Settings = RuntimeSettings & AdminSettings;
