"""Runtime settings: DB overrides (the `settings` table, JSON values) on top of env defaults.

Every behavioural setting is edited in the UI; its env var is only the initial default.
Secrets and boot-time infrastructure stay env-only and are never stored here.

Two tiers can be changed:

* runtime settings (`SettingsPatch`, admin role): sync, concurrency, grouping, limits, AI models;
* admin settings (`AdminSettingsPatch`, admin role + `ADMIN_PASSWORD`): bucket layout,
  publishing, source filters, sessions, login throttling and storage ACL / URL expiry.

`default_preset_id` is not stored here: it mirrors the preset flagged `is_default`.
Settings are read at use time through a short TTL cache. The process-wide Pillow
decompression-bomb limit (`max_image_megapixels`) is applied by `apply_image_limits`: at
startup and whenever settings are written, never as a side effect of reading them.

The use cases behind the Settings API (patching with an audit entry, database reset) live in
`settings_admin_service`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import MAX_PROCESS_CONCURRENCY, PREFIX_PATTERN, settings
from app.core import model_store
from app.core.derivatives import PublishConfig, check_names_against_sources
from app.core.source_filters import SourceFilters, SourceMatcher
from app.db.crud import get_all_settings, get_default_preset, recompute_group_keys, save_settings

logger = logging.getLogger(__name__)

S3Prefix = Annotated[str, StringConstraints(max_length=256, pattern=f"^{PREFIX_PATTERN.pattern}$")]
ModelName = Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$")]
ObjectAcl = Literal[
    "", "private", "public-read", "authenticated-read", "bucket-owner-read", "bucket-owner-full-control"
]
PREFIX_KEYS = ("source_prefix", "output_prefix", "backup_prefix")

# Bounded field types, shared by the output model and the patch models.
SyncIntervalMinutes = Annotated[int, Field(ge=0, le=24 * 60)]  # 0 disables auto-sync
ProcessConcurrency = Annotated[int, Field(ge=1, le=MAX_PROCESS_CONCURRENCY)]
AiConcurrency = Annotated[int, Field(ge=1, le=10)]
MaxRetryCount = Annotated[int, Field(ge=0, le=999)]
GroupDepth = Annotated[int, Field(ge=0, le=5)]
TransferMb = Annotated[int, Field(ge=1, le=200)]
Megapixels = Annotated[int, Field(ge=1, le=500)]
SessionMinutes = Annotated[int, Field(ge=5, le=7 * 24 * 60)]
LoginAttempts = Annotated[int, Field(ge=1, le=100)]
LockoutMinutes = Annotated[int, Field(ge=1, le=24 * 60)]
PresignSeconds = Annotated[int, Field(ge=60, le=7 * 24 * 3600)]


class SettingsOut(BaseModel):
    # Runtime (admin)
    sync_interval_minutes: SyncIntervalMinutes
    auto_process_after_sync: bool
    process_concurrency: ProcessConcurrency
    ai_concurrency: AiConcurrency
    max_retry_count: MaxRetryCount
    group_depth: GroupDepth
    default_preset_id: int | None = None
    max_upload_mb: TransferMb
    max_remote_fetch_mb: TransferMb
    max_image_megapixels: Megapixels
    openai_image_model: ModelName
    gemini_image_model: ModelName
    # Admin + step-up
    source_prefix: str
    output_prefix: str
    backup_prefix: str
    publish: PublishConfig = Field(default_factory=PublishConfig)
    source_filters: SourceFilters = Field(default_factory=SourceFilters)
    session_minutes: SessionMinutes
    login_max_attempts: LoginAttempts
    login_lockout_minutes: LockoutMinutes
    s3_object_acl: ObjectAcl
    presign_expires_seconds: PresignSeconds

    def source_matcher(self) -> SourceMatcher:
        return SourceMatcher(self.source_filters, self.publish)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_remote_fetch_bytes(self) -> int:
        return self.max_remote_fetch_mb * 1024 * 1024

    @property
    def max_image_pixels(self) -> int:
        return self.max_image_megapixels * 1_000_000


class SettingsPatch(BaseModel):
    """Runtime settings (admin role). `default_preset_id` switches the default preset."""

    model_config = ConfigDict(extra="forbid")  # step-up fields must go through PATCH /settings/admin

    sync_interval_minutes: SyncIntervalMinutes | None = None
    auto_process_after_sync: bool | None = None
    process_concurrency: ProcessConcurrency | None = None
    ai_concurrency: AiConcurrency | None = None
    max_retry_count: MaxRetryCount | None = None
    group_depth: GroupDepth | None = None
    default_preset_id: int | None = Field(None, ge=1)
    max_upload_mb: TransferMb | None = None
    max_remote_fetch_mb: TransferMb | None = None
    max_image_megapixels: Megapixels | None = None
    openai_image_model: ModelName | None = None
    gemini_image_model: ModelName | None = None


class AdminSettingsPatch(BaseModel):
    """Bucket layout, publishing, sessions, login throttling and storage (admin role + admin password)."""

    model_config = ConfigDict(extra="forbid")

    source_prefix: S3Prefix | None = None
    output_prefix: S3Prefix | None = None
    backup_prefix: S3Prefix | None = None
    publish: PublishConfig | None = None
    source_filters: SourceFilters | None = None
    session_minutes: SessionMinutes | None = None
    login_max_attempts: LoginAttempts | None = None
    login_lockout_minutes: LockoutMinutes | None = None
    s3_object_acl: ObjectAcl | None = None
    presign_expires_seconds: PresignSeconds | None = None
    admin_password: str = Field(max_length=256)

    @field_validator(*PREFIX_KEYS)
    @classmethod
    def _no_relative_segments(cls, value: str | None) -> str | None:
        if value is not None and any(part in ("", ".", "..") for part in value.rstrip("/").split("/")):
            raise ValueError("prefix must not contain empty, '.' or '..' segments")
        return value


class AdminVerifyRequest(BaseModel):
    admin_password: str = Field(max_length=256)


class AdminResetDbRequest(BaseModel):
    admin_password: str = Field(max_length=256)
    confirm: Literal["RESET"]


class InvalidSettings(ValueError):
    """A settings change that is inconsistent with the current settings; the message is safe to show."""


class EnvironmentOut(BaseModel):
    """Read-only facts about the deployment (env-only configuration). Holds no secrets."""

    app_name: str
    s3_bucket: str
    s3_endpoint_host: str
    s3_public_endpoint_host: str | None
    openai_configured: bool
    gemini_configured: bool
    api_docs_enabled: bool
    models_dir_writable: bool
    version: str


RUNTIME_KEYS = frozenset(SettingsPatch.model_fields) - {"default_preset_id"}
ADMIN_KEYS = frozenset(AdminSettingsPatch.model_fields) - {"admin_password"}
_STORED_KEYS = RUNTIME_KEYS | ADMIN_KEYS
_JSON_KEYS = frozenset({"publish", "source_filters"})  # defaults come from the models, not env
_GROUPING_KEYS = frozenset({"group_depth", "source_prefix"})


# ── Reading ───────────────────────────────────────────────────────────────────

_settings_cache: tuple[SettingsOut, float] | None = None
_SETTINGS_TTL = 30  # seconds


def invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None


def _env_defaults() -> dict[str, Any]:
    return {key: getattr(settings, key) for key in _STORED_KEYS - _JSON_KEYS}


def _merge(overrides: dict[str, str], default_preset_id: int | None) -> SettingsOut:
    values = _env_defaults()
    for key, raw in overrides.items():
        if key not in _STORED_KEYS:
            continue
        try:
            values[key] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Ignoring unreadable stored setting %r", key)
    try:
        return SettingsOut.model_validate({**values, "default_preset_id": default_preset_id})
    except ValidationError:
        logger.exception("Stored settings are invalid; falling back to defaults")
        return SettingsOut.model_validate({**_env_defaults(), "default_preset_id": default_preset_id})


async def get_runtime_settings(db: AsyncSession) -> SettingsOut:
    global _settings_cache
    now = time.monotonic()
    if _settings_cache is not None and _settings_cache[1] > now:
        return _settings_cache[0]
    default = await get_default_preset(db)
    result = _merge(await get_all_settings(db), default.id if default else None)
    _settings_cache = (result, now + _SETTINGS_TTL)
    return result


def apply_image_limits(rs: SettingsOut) -> None:
    """Set Pillow's process-wide decompression-bomb limit from `max_image_megapixels`.

    Call it wherever the stored settings may have changed: startup, updates and a database reset.
    """
    Image.MAX_IMAGE_PIXELS = rs.max_image_pixels


def _host_of(url: str) -> str | None:
    """`host[:port]` of a URL: never credentials, path or query."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname:
        return None
    return f"{parts.hostname}:{port}" if port else parts.hostname


def environment_info() -> EnvironmentOut:
    return EnvironmentOut(
        app_name=settings.app_name,
        s3_bucket=settings.s3_bucket,
        s3_endpoint_host=_host_of(settings.s3_endpoint_url) or "",
        s3_public_endpoint_host=_host_of(settings.s3_public_endpoint_url) if settings.s3_public_endpoint_url else None,
        openai_configured=bool(settings.openai_api_key),
        gemini_configured=bool(settings.gemini_api_key),
        api_docs_enabled=settings.api_docs_enabled,
        models_dir_writable=model_store.is_models_dir_writable(),
        version=__version__,
    )


# ── Writing ───────────────────────────────────────────────────────────────────


def validate_admin_changes(current: SettingsOut, updates: dict[str, Any]) -> None:
    """Cross-field checks: distinct, non-nested prefixes; derivatives never overwrite sources."""
    prefixes = [updates.get(key, getattr(current, key)) for key in PREFIX_KEYS]
    if len(set(prefixes)) != len(prefixes):
        raise InvalidSettings("source_prefix, output_prefix and backup_prefix must all be distinct")
    if any(a != b and (a.startswith(b) or b.startswith(a)) for a in prefixes for b in prefixes):
        raise InvalidSettings("Prefixes must not be nested inside each other")

    publish = PublishConfig.model_validate(updates.get("publish", current.publish))
    filters = SourceFilters.model_validate(updates.get("source_filters", current.source_filters))
    try:
        check_names_against_sources(publish, filters.extensions)
    except ValueError as exc:
        raise InvalidSettings(str(exc)) from exc


async def update_settings(db: AsyncSession, updates: dict[str, Any]) -> SettingsOut:
    """Persist already-validated overrides (JSON-encoded); regroup images when grouping changed."""
    unknown = set(updates) - _STORED_KEYS
    if unknown:
        raise ValueError(f"Not runtime settings: {sorted(unknown)}")
    if not updates:
        return await get_runtime_settings(db)

    before = await get_runtime_settings(db)
    await save_settings(db, {key: json.dumps(value) for key, value in updates.items()})
    invalidate_settings_cache()
    after = await get_runtime_settings(db)
    apply_image_limits(after)

    if any(getattr(before, key) != getattr(after, key) for key in _GROUPING_KEYS):
        changed = await recompute_group_keys(db, after.source_prefix, after.group_depth)
        logger.info("Recomputed group_key for %d image(s)", changed)
    return after
