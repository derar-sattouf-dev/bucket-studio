"""Application settings, loaded from environment variables (and `.env` when present).

Every field maps to an upper-case env var of the same name (matching is case-insensitive).

Two kinds of fields live here:

* boot-time infrastructure and secrets (env only, never stored in the DB);
* initial defaults for runtime settings, which are edited in the UI and stored in the
  `settings` table. Read those through `app.services.settings_service`, never from here.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MIN_SECRET_LENGTH = 32
_MIN_ADMIN_PASSWORD_LENGTH = 8
_MIN_API_KEY_LENGTH = 16

# A bucket prefix: one or more folder names, ending with "/". The single definition of the rule,
# used for the environment values here and for changes made through the settings API.
PREFIX_PATTERN = re.compile(r"[A-Za-z0-9!_.*'()\-][A-Za-z0-9!_.*'()/\-]{0,254}/")
# Upper bound of the `process_concurrency` setting; the pipeline's thread pool is sized to it.
MAX_PROCESS_CONCURRENCY = 16
_BACKEND_DIR = Path(__file__).resolve().parent.parent

# The repo-root .env (used by Docker Compose) and an optional backend/.env; later files win. Paths are
# absolute so uvicorn finds them from any directory; missing files are ignored. The test suite sets
# BUCKET_STUDIO_DOTENV=0 so a developer's local .env never leaks into tests.
_ENV_FILES = (
    (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env") if os.environ.get("BUCKET_STUDIO_DOTENV", "1") != "0" else ()
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    app_name: str = "Bucket Studio"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Secret used to sign JWTs. Generate with `openssl rand -hex 32`.
    jwt_secret: str = ""
    jwt_issuer: str = "bucket-studio"

    # Bootstrap admin account (always has the admin role).
    auth_username: str = ""
    auth_password: str = ""

    # Step-up password required for destructive / sensitive admin actions.
    admin_password: str = ""

    # Optional static key for server-to-server integrations (sent as `X-API-Key`).
    # Never expose it to the browser. Leave empty to disable.
    api_key: str = ""

    # ── HTTP ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Expose Swagger UI / OpenAPI schema. Off unless asked for (the dev stack turns it on).
    api_docs_enabled: bool = False

    # ── S3-compatible storage ─────────────────────────────────────────────────
    s3_endpoint_url: str = "http://localhost:9000"
    # Endpoint used only to sign browser-facing URLs (e.g. http://localhost:9000 when the
    # backend reaches MinIO as http://minio:9000). Empty = same as s3_endpoint_url.
    s3_public_endpoint_url: str = ""
    # Leave both empty to use the standard AWS credential chain (instance profile, IRSA, env, ...).
    s3_access_key: str = ""
    s3_secret_key: str = ""
    # "auto" lets the SDK decide; "path" (bucket in the path) suits MinIO and most self-hosted
    # stores; "virtual" (bucket in the host name) is what AWS and some providers require.
    s3_addressing_style: Literal["auto", "path", "virtual"] = "auto"
    # "when_required" sends integrity checksums only where the API demands them, which works with
    # every S3-compatible provider. Newer SDKs default to "when_supported" (extra CRC headers),
    # which some non-AWS providers reject.
    s3_checksum_mode: Literal["when_required", "when_supported"] = "when_required"
    s3_bucket: str = "bucket-studio"
    s3_region: str = "us-east-1"
    # Create the bucket on startup if it is missing (local development with MinIO).
    s3_auto_create_bucket: bool = False

    # ── Storage paths ─────────────────────────────────────────────────────────
    # Directory for the SQLite database. Defaults to backend/data.
    data_dir: str = ""
    # Directory for ML weights (Real-ESRGAN, rembg), downloaded on first use. Defaults to backend/models.
    models_dir: str = ""

    # ── AI provider keys (optional; each one enables an engine) ───────────────
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # ── Initial defaults for runtime settings (validated by the settings service) ──
    # Processing and sync
    sync_interval_minutes: int = 30
    auto_process_after_sync: bool = False
    process_concurrency: int = 2
    ai_concurrency: int = 2
    max_retry_count: int = 999
    group_depth: int = 1
    # Limits
    max_upload_mb: int = 20
    max_remote_fetch_mb: int = 20
    max_image_megapixels: int = 80  # decompression-bomb guard for every Pillow decode
    # AI models
    openai_image_model: str = "gpt-image-1.5"
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    # Bucket layout (admin + step-up)
    source_prefix: str = "images/"
    output_prefix: str = "processed/"
    backup_prefix: str = "backup/"
    # Security and storage (admin + step-up)
    session_minutes: int = 60 * 12
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    # Canned ACL for written objects. Default: none, which works with buckets that have ACLs disabled
    # (the AWS default). Use "public-read" only if images must be publicly readable via ACLs.
    s3_object_acl: str = ""
    presign_expires_seconds: int = 3600

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_strength(cls, value: str) -> str:
        if value and len(value) < _MIN_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET must be at least {_MIN_SECRET_LENGTH} characters "
                "(generate one with `openssl rand -hex 32`)"
            )
        return value

    @field_validator("admin_password")
    @classmethod
    def _admin_password_strength(cls, value: str) -> str:
        if value and len(value) < _MIN_ADMIN_PASSWORD_LENGTH:
            raise ValueError(f"ADMIN_PASSWORD must be at least {_MIN_ADMIN_PASSWORD_LENGTH} characters")
        return value

    @field_validator("api_key")
    @classmethod
    def _api_key_strength(cls, value: str) -> str:
        if value and len(value) < _MIN_API_KEY_LENGTH:
            raise ValueError(
                f"API_KEY must be at least {_MIN_API_KEY_LENGTH} characters (generate one with `openssl rand -hex 24`)"
            )
        return value

    @model_validator(mode="after")
    def _prefix_layout(self) -> Settings:
        """The same rules the settings API enforces, applied to the environment's initial values:
        a prefix that is empty, nested or shared would let a source key resolve into the outputs
        or backups."""
        prefixes = {
            "SOURCE_PREFIX": self.source_prefix,
            "OUTPUT_PREFIX": self.output_prefix,
            "BACKUP_PREFIX": self.backup_prefix,
        }
        for name, value in prefixes.items():
            if not PREFIX_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a folder path ending with '/', e.g. 'images/' (got {value!r})")
        values = list(prefixes.values())
        if len(set(values)) != len(values):
            raise ValueError("SOURCE_PREFIX, OUTPUT_PREFIX and BACKUP_PREFIX must all be different")
        if any(a != b and a.startswith(b) for a in values for b in values):
            raise ValueError("SOURCE_PREFIX, OUTPUT_PREFIX and BACKUP_PREFIX must not be nested inside each other")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def models_path(self) -> Path:
        return Path(self.models_dir) if self.models_dir else _BACKEND_DIR / "models"


settings = Settings()
