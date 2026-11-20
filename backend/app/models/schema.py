"""Pydantic request / response models for the HTTP API."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.job_registry import JobStatus
from app.core.net import MAX_URL_LENGTH
from app.core.passwords import MIN_PASSWORD_LENGTH
from app.core.preset_config import MAX_PROMPT_LENGTH, PresetConfig
from app.core.rendering import EngineChoice
from app.db.crud import ImageListStatus
from app.db.models import ImageStatus


def _as_utc(value: datetime) -> datetime:
    """Timestamps are stored as naive UTC (SQLite); mark them so clients convert to local time."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]

MAX_KEYS_PER_REQUEST = 500
MAX_IMPORT_URLS = 100

SourceKey = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
KeyList = Annotated[list[SourceKey], Field(min_length=1, max_length=MAX_KEYS_PER_REQUEST)]
# A sub-prefix for one batch job; the job service confines it to the configured source/output prefix.
JobPrefix = Annotated[str, StringConstraints(max_length=256, pattern=r"^[A-Za-z0-9!_.*'()/\-]*$")]
Prompt = Annotated[str, StringConstraints(min_length=1, max_length=MAX_PROMPT_LENGTH)]
PresetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
PresetDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
GroupKey = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
SearchText = Annotated[str, StringConstraints(max_length=200)]
RemoteUrl = Annotated[str, StringConstraints(min_length=1, max_length=MAX_URL_LENGTH)]


# ── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str
    expires_in: int


class MeResponse(BaseModel):
    username: str
    is_admin: bool


# ── Stats ─────────────────────────────────────────────────────────────────────


class StatsOut(BaseModel):
    total: int
    pending: int
    processing: int
    processed: int
    failed: int
    published: int
    job_running: bool
    ai_processed: int = 0
    avg_seconds_per_image: float | None = None


# ── Activity log ──────────────────────────────────────────────────────────────


class ActivityLogOut(BaseModel):
    id: int
    event_type: str
    message: str
    meta: str | None = None
    username: str | None = None
    created_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class BatchHistoryOut(BaseModel):
    id: int
    job_id: str
    source_prefix: str
    status: str
    total: int
    processed: int
    failed: int
    skipped: int
    started_at: UtcDatetime | None
    completed_at: UtcDatetime
    elapsed_seconds: float | None

    model_config = ConfigDict(from_attributes=True)


# ── Users ─────────────────────────────────────────────────────────────────────


class UserOut(BaseModel):
    id: int
    username: str
    created_at: UtcDatetime
    is_active: bool
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    # The full policy (also a 72-byte cap, see core/passwords.py) is enforced by the user service.
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    is_admin: bool = False
    admin_password: str = Field(max_length=256)


class UpdateUserRequest(BaseModel):
    """Activate or deactivate a user. A deactivated user cannot sign in and loses access at once."""

    is_active: bool
    admin_password: str = Field(max_length=256)


class DeleteUserRequest(BaseModel):
    admin_password: str = Field(max_length=256)


# ── Presets ───────────────────────────────────────────────────────────────────


class PresetOut(BaseModel):
    id: int
    name: str
    description: str
    config: PresetConfig
    is_default: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class PresetCreate(BaseModel):
    name: PresetName
    description: PresetDescription = ""
    config: PresetConfig = Field(default_factory=PresetConfig)


class PresetUpdate(BaseModel):
    """`config`, when given, replaces the stored config (missing fields take their defaults)."""

    name: PresetName | None = None
    description: PresetDescription | None = None
    config: PresetConfig | None = None


# ── Jobs ──────────────────────────────────────────────────────────────────────


class StartJobRequest(BaseModel):
    """All fields optional; prefixes must stay inside the configured source / output prefixes."""

    source_prefix: JobPrefix | None = None
    output_prefix: JobPrefix | None = None
    preset_id: int | None = Field(None, ge=1)
    overwrite_original: bool | None = None


class JobError(BaseModel):
    key: str
    error: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    total: int
    processed: int
    failed: int
    skipped: int
    progress_pct: float
    elapsed_seconds: float | None
    errors: list[JobError]
    current_key: str | None
    bucket: str
    source_prefix: str
    output_prefix: str
    overwrite: bool
    preset_id: int
    preset_name: str


# ── Images ────────────────────────────────────────────────────────────────────


class ImageOut(BaseModel):
    id: int
    source_key: str
    processed_key: str | None
    status: ImageStatus
    source_size: int | None
    processed_size: int | None
    discovered_at: UtcDatetime | None = None
    processed_at: UtcDatetime | None
    updated_at: UtcDatetime  # last status change (e.g. the last failed attempt)
    error_message: str | None
    retry_count: int = 0
    notes: str | None = None
    tags: str | None = None
    processed_by: str | None = None
    group_key: str | None = None
    preset_id: int | None = None
    is_published: bool = False
    source_width: int | None = None
    source_height: int | None = None
    source_url: str | None = None
    processed_url: str | None = None
    backup_url: str | None = None
    derivative_urls: dict[str, str] = Field(default_factory=dict)
    is_processing: bool = False

    model_config = ConfigDict(from_attributes=True)


class ImageGroupOut(BaseModel):
    group: str | None
    images: list[ImageOut]  # the first images of the group; the rest come from GET /images/group
    image_count: int  # every image of the group that matches the list filters
    publishable_count: int


class PaginatedGroups(BaseModel):
    items: list[ImageGroupOut]
    grouped: bool  # False: grouping is off and `items` is one page of images in a single null group
    total_images: int
    total_groups: int
    page: int
    page_size: int
    total_pages: int


class PaginatedImages(BaseModel):
    items: list[ImageOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class GroupImagesPage(BaseModel):
    group: str | None
    items: list[ImageOut]
    total: int
    offset: int
    limit: int


class GroupSelector(BaseModel):
    """The images of one group that match the list filters; `group` null = the ungrouped images."""

    group: GroupKey | None = None
    status: ImageListStatus | None = None
    search: SearchText | None = None


class UpdateNotesRequest(BaseModel):
    source_key: SourceKey
    notes: str | None = Field(None, max_length=5000)
    tags: str | None = Field(None, max_length=512)


class ProcessRequest(BaseModel):
    keys: KeyList
    preset_id: int | None = Field(None, ge=1)  # None = default preset
    engine: EngineChoice = "preset"
    prompt: Prompt | None = None
    replace: bool = False  # overwrite the original in place (admin only, no backup)


class ProcessGroupRequest(GroupSelector):
    preset_id: int | None = Field(None, ge=1)
    engine: EngineChoice = "preset"
    prompt: Prompt | None = None
    replace: bool = False


class BulkPublishError(BaseModel):
    key: str
    error: str


class BulkPublishStatus(BaseModel):
    running: bool
    total: int
    done: int
    published: int
    failed: int
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    errors: list[BulkPublishError]  # the first failures only


class RetryFailedResult(BaseModel):
    queued: int
    skipped_max_retries: int  # failed images that already reached the retry limit
    skipped_other: int  # below the limit but not requeued: already being processed, or no longer a source


class AbortRequest(BaseModel):
    key: SourceKey


class KeysRequest(BaseModel):
    keys: KeyList


# ── Imports ───────────────────────────────────────────────────────────────────


class ImportRequest(BaseModel):
    urls: list[RemoteUrl] = Field(min_length=1, max_length=MAX_IMPORT_URLS)
    # Folder relative to source_prefix, '' for the prefix itself, e.g. 'summer/shoes/'.
    folder: str = Field("", max_length=256, pattern=r"^([A-Za-z0-9._-]+/)*$")

    @model_validator(mode="after")
    def _no_relative_segments(self) -> "ImportRequest":
        if any(part in (".", "..") for part in self.folder.split("/")):
            raise ValueError("folder must not contain '.' or '..' segments")
        return self


class ImportedImage(BaseModel):
    url: str
    key: str
    size: int


class FailedImport(BaseModel):
    url: str
    error: str


class ImportResult(BaseModel):
    imported: list[ImportedImage]
    failed: list[FailedImport]


# ── Playground ────────────────────────────────────────────────────────────────


class PlaygroundUrlRequest(BaseModel):
    """Exactly one of `preset_id` and `config`."""

    url: RemoteUrl
    preset_id: int | None = Field(None, ge=1)
    config: PresetConfig | None = None
    engine: EngineChoice = "preset"

    @model_validator(mode="after")
    def _one_source(self) -> "PlaygroundUrlRequest":
        if (self.preset_id is None) == (self.config is None):
            raise ValueError("Give exactly one of preset_id and config")
        return self
