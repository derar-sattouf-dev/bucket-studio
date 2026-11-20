"""SQLAlchemy ORM models. Schema changes need an Alembic revision (see app/db/migrations)."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ImageStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class ImageRecord(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # S3 keys
    source_key: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    processed_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Status
    status: Mapped[ImageStatus] = mapped_column(Enum(ImageStatus), default=ImageStatus.PENDING, index=True)

    # Sizes in bytes
    source_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    processed_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Folder-based group: the first `group_depth` folders after source_prefix (None = ungrouped)
    group_key: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    # Preset used for the last processing attempt
    preset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("presets.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # What produced the output: "local", "openai:<model>" or "gemini:<model>"
    processed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Set when the processed image is published over the source, cleared on restore
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Where the original was copied before publish overwrote the source. Stored per image (not derived
    # from the current backup prefix) and set *before* the overwrite, so a publish that fails half-way
    # or a later prefix change can never lose the original. Cleared once the original is restored.
    backup_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Source image dimensions (populated at process time)
    source_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # User annotations
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(512), nullable=True)  # comma-separated


class SettingRecord(Base):
    """Key-value store for runtime-overridable settings."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ActivityLog(Base):
    """Append-only audit log of system events."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class BatchJobHistory(Base):
    """Persisted record of every completed batch job."""

    __tablename__ = "batch_job_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True)
    source_prefix: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32))  # completed / stopped / failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class Preset(Base):
    """A named processing configuration (`PresetConfig` JSON). Exactly one is the default."""

    __tablename__ = "presets"
    __table_args__ = (
        # At most one default at the database level; the service keeps it at exactly one.
        Index("uq_presets_single_default", "is_default", unique=True, sqlite_where=text("is_default = 1")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    config: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    """Application users (in addition to the env-var admin)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
