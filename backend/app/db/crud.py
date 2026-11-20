"""All database queries in one place."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import ColumnElement, CursorResult, Select, and_, case, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from app.core.source_filters import group_key_of
from app.db.models import ActivityLog, BatchJobHistory, ImageRecord, ImageStatus, Preset, SettingRecord, User

ABORTED_MESSAGE = "Aborted by user"
MAX_ERROR_MESSAGE_LENGTH = 500

ImageListStatus = Literal["pending", "processing", "processed", "failed", "published"]
ImageSortField = Literal["id", "source_size", "processed_size", "processed_at", "discovered_at", "updated_at"]

_SORTABLE = {
    "id": ImageRecord.id,
    "source_size": ImageRecord.source_size,
    "processed_size": ImageRecord.processed_size,
    "processed_at": ImageRecord.processed_at,
    "discovered_at": ImageRecord.discovered_at,
    "updated_at": ImageRecord.updated_at,
}


def _now() -> datetime:
    return datetime.now(UTC)


async def _execute_dml(db: AsyncSession, stmt: Executable) -> CursorResult[Any]:
    """Run an INSERT / UPDATE / DELETE; its result is a `CursorResult`, which carries `rowcount`."""
    result = await db.execute(stmt)
    if not isinstance(result, CursorResult):  # always a CursorResult for DML; this narrows the type
        raise TypeError("expected a DML statement")
    return result


# ── Upsert (used during S3 sync and imports) ──────────────────────────────────


async def upsert_images(
    db: AsyncSession,
    keys_sizes: Sequence[tuple[str, int]],
    source_prefix: str,
    group_depth: int,
) -> int:
    """Insert unseen source images as pending. Returns the number of new rows."""
    rows = {
        key: {"source_key": key, "source_size": size, "group_key": group_key_of(key, source_prefix, group_depth)}
        for key, size in keys_sizes
    }
    if not rows:
        return 0
    stmt = insert(ImageRecord).values(list(rows.values())).on_conflict_do_nothing(index_elements=["source_key"])
    result = await _execute_dml(db, stmt)
    await db.commit()
    return result.rowcount


async def recompute_group_keys(db: AsyncSession, source_prefix: str, group_depth: int) -> int:
    """Recompute every image's group_key (after `group_depth` or `source_prefix` changed)."""
    rows = (await db.execute(select(ImageRecord.id, ImageRecord.source_key, ImageRecord.group_key))).all()
    changes = [
        {"id": row.id, "group_key": new}
        for row in rows
        if (new := group_key_of(row.source_key, source_prefix, group_depth)) != row.group_key
    ]
    if changes:
        await db.execute(update(ImageRecord), changes)
        await db.commit()
    return len(changes)


# ── Grouped paginated list ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImageGroup:
    group: str | None
    images: list[ImageRecord]  # the first images of the group, not necessarily all of them
    image_count: int  # every image of the group that matches the list filters
    publishable_count: int  # of those, the ones a publish would take


@dataclass(frozen=True)
class GroupedPage:
    groups: list[ImageGroup]
    total_images: int
    total_groups: int


@dataclass(frozen=True)
class GroupScope:
    """The images of one group (`None`: the ungrouped ones) that match the list filters."""

    group: str | None
    status: ImageListStatus | None = None
    search: str | None = None


def _reviewable() -> tuple[ColumnElement[bool], ...]:
    """Processed, not yet published, with a separate processed output to publish."""
    return (
        ImageRecord.status == ImageStatus.PROCESSED,
        ImageRecord.is_published.is_(False),
        ImageRecord.processed_key.isnot(None),
        ImageRecord.processed_key != ImageRecord.source_key,
    )


def _list_filters(q: Select, status: ImageListStatus | None, search: str | None) -> Select:
    if status == "published":
        q = q.where(ImageRecord.is_published.is_(True))
    elif status == "processed":
        q = q.where(ImageRecord.status == ImageStatus.PROCESSED, ImageRecord.is_published.is_(False))
    elif status:
        q = q.where(ImageRecord.status == ImageStatus(status))
    if search:
        q = q.where(ImageRecord.source_key.contains(search, autoescape=True))
    return q


def _in_scope(q: Select, scope: GroupScope) -> Select:
    in_group = ImageRecord.group_key.is_(None) if scope.group is None else ImageRecord.group_key == scope.group
    return _list_filters(q.where(in_group), scope.status, scope.search)


def _record_order(sort_by: ImageSortField, sort_order: Literal["asc", "desc"]) -> tuple[Any, Any]:
    col = _SORTABLE.get(sort_by, ImageRecord.id)
    return (col.desc() if sort_order == "desc" else col.asc()), ImageRecord.id


async def list_images_grouped(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    grouped: bool,
    per_group: int,
    status: ImageListStatus | None = None,
    search: str | None = None,
    sort_by: ImageSortField = "id",
    sort_order: Literal["asc", "desc"] = "desc",
) -> GroupedPage:
    """One page of images grouped by `group_key`, with at most `per_group` images of each group.

    The rest of a group is read with `list_group_images`. With `grouped=False` pagination is
    over images and the page is a single group (None). Images without a group key form their
    own group (None) when grouping is on.
    """
    col = _SORTABLE.get(sort_by, ImageRecord.id)
    record_order = _record_order(sort_by, sort_order)
    offset = (page - 1) * page_size
    total_images = await db.scalar(_list_filters(select(func.count()).select_from(ImageRecord), status, search)) or 0

    if not grouped:
        records = list(
            await db.scalars(
                _list_filters(select(ImageRecord), status, search)
                .order_by(*record_order)
                .limit(page_size)
                .offset(offset)
            )
        )
        publishable = sum(
            r.status == ImageStatus.PROCESSED and not r.is_published and r.processed_key not in (None, r.source_key)
            for r in records
        )
        groups = [ImageGroup(None, records, len(records), publishable)] if records else []
        return GroupedPage(groups, total_images, 1 if total_images else 0)

    group_order = func.max(col).desc() if sort_order == "desc" else func.min(col).asc()
    publishable = func.sum(case((and_(*_reviewable()), 1), else_=0))
    groups_q = _list_filters(
        select(ImageRecord.group_key, func.count().label("image_count"), publishable.label("publishable_count"))
        .group_by(ImageRecord.group_key)
        .order_by(group_order, ImageRecord.group_key),
        status,
        search,
    )
    total_groups = await db.scalar(select(func.count()).select_from(groups_q.subquery())) or 0
    page_groups = (await db.execute(groups_q.limit(page_size).offset(offset))).all()
    if not page_groups:
        return GroupedPage([], total_images, total_groups)

    page_keys = [row.group_key for row in page_groups]
    named = [k for k in page_keys if k is not None]
    membership: ColumnElement[bool] = ImageRecord.group_key.in_(named)
    if None in page_keys:
        membership = or_(membership, ImageRecord.group_key.is_(None))
    position = func.row_number().over(partition_by=ImageRecord.group_key, order_by=record_order).label("position")
    ranked = _list_filters(select(ImageRecord.id, position).where(membership), status, search).subquery()
    page_records = await db.scalars(
        select(ImageRecord)
        .join(ranked, ImageRecord.id == ranked.c.id)
        .where(ranked.c.position <= per_group)
        .order_by(*record_order)
    )

    by_group: dict[str | None, list[ImageRecord]] = {k: [] for k in page_keys}
    for record in page_records:
        by_group[record.group_key].append(record)
    return GroupedPage(
        [ImageGroup(g.group_key, by_group[g.group_key], g.image_count, g.publishable_count or 0) for g in page_groups],
        total_images,
        total_groups,
    )


async def list_group_images(
    db: AsyncSession,
    scope: GroupScope,
    *,
    offset: int,
    limit: int,
    sort_by: ImageSortField = "id",
    sort_order: Literal["asc", "desc"] = "desc",
) -> tuple[list[ImageRecord], int]:
    """A slice of one group's images (same filters and order as the grouped list) and the group's size."""
    total = await db.scalar(_in_scope(select(func.count()).select_from(ImageRecord), scope)) or 0
    records = await db.scalars(
        _in_scope(select(ImageRecord), scope).order_by(*_record_order(sort_by, sort_order)).limit(limit).offset(offset)
    )
    return list(records), total


async def get_group_keys(db: AsyncSession, scope: GroupScope) -> list[str]:
    """Source keys of every image in a group; keys only, so a huge group stays cheap."""
    return list(await db.scalars(_in_scope(select(ImageRecord.source_key), scope).order_by(ImageRecord.id)))


# ── Fetch ─────────────────────────────────────────────────────────────────────


async def get_image_by_key(db: AsyncSession, source_key: str) -> ImageRecord | None:
    return await db.scalar(select(ImageRecord).where(ImageRecord.source_key == source_key))


async def get_images_by_keys(db: AsyncSession, keys: Sequence[str]) -> list[ImageRecord]:
    if not keys:
        return []
    result = await db.scalars(select(ImageRecord).where(ImageRecord.source_key.in_(keys)))
    return list(result)


async def get_processed_keys(db: AsyncSession) -> set[str]:
    result = await db.scalars(select(ImageRecord.source_key).where(ImageRecord.status == ImageStatus.PROCESSED))
    return set(result)


async def is_processed(db: AsyncSession, source_key: str) -> bool:
    status = await db.scalar(select(ImageRecord.status).where(ImageRecord.source_key == source_key))
    return status == ImageStatus.PROCESSED


def _failed() -> tuple[ColumnElement[bool], ...]:
    """Failed images, excluding ones a user aborted."""
    return (
        ImageRecord.status == ImageStatus.FAILED,
        or_(ImageRecord.error_message.is_(None), ImageRecord.error_message != ABORTED_MESSAGE),
    )


@dataclass(frozen=True)
class ImagePage:
    records: list[ImageRecord]
    total: int


async def _page(db: AsyncSession, q: Select, order: Sequence[Any], page: int, page_size: int) -> ImagePage:
    total = await db.scalar(select(func.count()).select_from(q.subquery())) or 0
    records = await db.scalars(q.order_by(*order).limit(page_size).offset((page - 1) * page_size))
    return ImagePage(list(records), total)


async def list_failed_images(db: AsyncSession, *, page: int, page_size: int, search: str | None = None) -> ImagePage:
    """One page of failed images, newest failure first; `search` matches the key or the error."""
    q = select(ImageRecord).where(*_failed())
    if search:
        q = q.where(
            or_(
                ImageRecord.source_key.contains(search, autoescape=True),
                ImageRecord.error_message.contains(search, autoescape=True),
            )
        )
    return await _page(db, q, (ImageRecord.updated_at.desc(), ImageRecord.id.desc()), page, page_size)


async def count_failed_images(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(ImageRecord).where(*_failed())) or 0


async def get_retryable_failed_keys(db: AsyncSession, max_retries: int) -> list[str]:
    """Source keys of failed images that were tried fewer than `max_retries` times."""
    q = select(ImageRecord.source_key).where(*_failed(), ImageRecord.retry_count < max_retries)
    return list(await db.scalars(q.order_by(ImageRecord.id)))


async def list_review_candidates(
    db: AsyncSession, *, page: int, page_size: int, search: str | None = None
) -> ImagePage:
    """One page of the images waiting to be published, most recently processed first."""
    q = select(ImageRecord).where(*_reviewable())
    if search:
        q = q.where(ImageRecord.source_key.contains(search, autoescape=True))
    return await _page(db, q, (ImageRecord.processed_at.desc(), ImageRecord.id.desc()), page, page_size)


async def get_review_candidate_keys(db: AsyncSession, scope: GroupScope | None = None) -> list[str]:
    """Source keys of every image waiting to be published (optionally of one group); keys only."""
    q = select(ImageRecord.source_key).where(*_reviewable())
    if scope is not None:
        q = _in_scope(q, scope)
    return list(await db.scalars(q.order_by(ImageRecord.id)))


# ── Status updates ────────────────────────────────────────────────────────────


async def mark_processing(db: AsyncSession, source_key: str, preset_id: int | None) -> None:
    await db.execute(
        update(ImageRecord)
        .where(ImageRecord.source_key == source_key)
        .values(status=ImageStatus.PROCESSING, error_message=None, preset_id=preset_id, updated_at=_now())
    )
    await db.commit()


async def mark_processed(
    db: AsyncSession,
    source_key: str,
    processed_key: str,
    processed_size: int,
    processed_by: str | None = None,
    source_width: int | None = None,
    source_height: int | None = None,
) -> None:
    now = _now()
    values: dict[str, Any] = {
        "status": ImageStatus.PROCESSED,
        "processed_key": processed_key,
        "processed_size": processed_size,
        "processed_at": now,
        "updated_at": now,
        "error_message": None,
        "processed_by": processed_by,
    }
    if source_width is not None:
        values["source_width"] = source_width
    if source_height is not None:
        values["source_height"] = source_height
    await db.execute(update(ImageRecord).where(ImageRecord.source_key == source_key).values(**values))
    await db.commit()


async def mark_failed(db: AsyncSession, source_key: str, error: str) -> None:
    await db.execute(
        update(ImageRecord)
        .where(ImageRecord.source_key == source_key)
        .values(
            status=ImageStatus.FAILED,
            error_message=error[:MAX_ERROR_MESSAGE_LENGTH],
            retry_count=ImageRecord.retry_count + 1,
            updated_at=_now(),
        )
    )
    await db.commit()


async def mark_aborted(db: AsyncSession, source_key: str) -> None:
    await db.execute(
        update(ImageRecord)
        .where(ImageRecord.source_key == source_key)
        .values(status=ImageStatus.FAILED, error_message=ABORTED_MESSAGE, updated_at=_now())
    )
    await db.commit()


async def set_backup_key(db: AsyncSession, source_key: str, backup_key: str) -> None:
    """Record where the original was backed up (written before publish overwrites the source)."""
    await db.execute(
        update(ImageRecord).where(ImageRecord.source_key == source_key).values(backup_key=backup_key, updated_at=_now())
    )
    await db.commit()


async def mark_published(db: AsyncSession, source_key: str, processed_size: int) -> None:
    """Mark an image as published (its processed output now lives at the source key)."""
    now = _now()
    await db.execute(
        update(ImageRecord)
        .where(ImageRecord.source_key == source_key)
        .values(
            status=ImageStatus.PROCESSED,
            processed_key=source_key,
            processed_size=processed_size,
            processed_at=now,
            updated_at=now,
            error_message=None,
            is_published=True,
        )
    )
    await db.commit()


async def mark_pending_many(db: AsyncSession, source_keys: list[str]) -> int:
    """Reset images to pending (clears the processed output, the published flag and the backup pointer)."""
    if not source_keys:
        return 0
    result = await _execute_dml(
        db,
        update(ImageRecord)
        .where(ImageRecord.source_key.in_(source_keys))
        .values(
            status=ImageStatus.PENDING,
            processed_key=None,
            processed_size=None,
            processed_at=None,
            updated_at=_now(),
            error_message=None,
            is_published=False,
            backup_key=None,
        ),
    )
    await db.commit()
    return result.rowcount


async def recover_stuck_images(db: AsyncSession) -> int:
    """Put images left in `processing` by a previous process back to pending. Returns how many."""
    result = await _execute_dml(
        db,
        update(ImageRecord)
        .where(ImageRecord.status == ImageStatus.PROCESSING)
        .values(status=ImageStatus.PENDING, error_message="Recovered after server restart"),
    )
    await db.commit()
    return result.rowcount


# ── Settings ──────────────────────────────────────────────────────────────────


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    rows = await db.scalars(select(SettingRecord))
    return {r.key: r.value for r in rows}


async def save_settings(db: AsyncSession, updates: dict[str, str]) -> None:
    for key, value in updates.items():
        stmt = (
            insert(SettingRecord)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": func.now()},
            )
        )
        await db.execute(stmt)
    await db.commit()


# ── Stats ─────────────────────────────────────────────────────────────────────


async def get_image_stats(db: AsyncSession) -> dict[str, Any]:
    rows = await db.execute(select(ImageRecord.status, func.count().label("cnt")).group_by(ImageRecord.status))
    counts = {ImageStatus(r.status).value: r.cnt for r in rows}
    published = await db.scalar(select(func.count()).where(ImageRecord.is_published.is_(True)))
    ai_processed = await db.scalar(
        select(func.count()).where(
            or_(ImageRecord.processed_by.startswith("openai:"), ImageRecord.processed_by.startswith("gemini:"))
        )
    )

    recent_job = await db.scalar(
        select(BatchJobHistory)
        .where(BatchJobHistory.processed > 0, BatchJobHistory.elapsed_seconds.isnot(None))
        .order_by(BatchJobHistory.completed_at.desc())
        .limit(1)
    )
    avg_seconds_per_image = None
    if recent_job is not None and recent_job.elapsed_seconds is not None:
        avg_seconds_per_image = round(recent_job.elapsed_seconds / recent_job.processed, 1)

    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "processing": counts.get("processing", 0),
        "processed": counts.get("processed", 0),
        "failed": counts.get("failed", 0),
        "published": published or 0,
        "ai_processed": ai_processed or 0,
        "avg_seconds_per_image": avg_seconds_per_image,
    }


# ── Activity log ──────────────────────────────────────────────────────────────


async def log_activity(
    db: AsyncSession,
    event_type: str,
    message: str,
    meta: dict[str, Any] | None = None,
    username: str | None = None,
) -> None:
    db.add(
        ActivityLog(
            event_type=event_type,
            message=message,
            meta=json.dumps(meta) if meta else None,
            username=username,
        )
    )
    await db.commit()


async def get_activity_log(db: AsyncSession, limit: int = 50, search: str = "") -> list[ActivityLog]:
    q = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    if search:
        q = q.where(
            or_(
                ActivityLog.message.contains(search, autoescape=True),
                ActivityLog.username.contains(search, autoescape=True),
                ActivityLog.event_type.contains(search, autoescape=True),
            )
        )
    result = await db.scalars(q.limit(limit))
    return list(result)


# ── Batch job history ─────────────────────────────────────────────────────────


async def save_batch_history(
    db: AsyncSession,
    job_id: str,
    source_prefix: str,
    status: str,
    total: int,
    processed: int,
    failed: int,
    skipped: int,
    started_at: datetime | None,
    completed_at: datetime,
    elapsed_seconds: float | None,
) -> None:
    stmt = (
        insert(BatchJobHistory)
        .values(
            job_id=job_id,
            source_prefix=source_prefix,
            status=status,
            total=total,
            processed=processed,
            failed=failed,
            skipped=skipped,
            started_at=started_at,
            completed_at=completed_at,
            elapsed_seconds=elapsed_seconds,
        )
        .on_conflict_do_nothing(index_elements=["job_id"])
    )
    await db.execute(stmt)
    await db.commit()


async def get_batch_history(db: AsyncSession, limit: int = 30) -> list[BatchJobHistory]:
    result = await db.scalars(select(BatchJobHistory).order_by(BatchJobHistory.completed_at.desc()).limit(limit))
    return list(result)


# ── Image notes / tags ────────────────────────────────────────────────────────


async def update_image_notes(
    db: AsyncSession,
    source_key: str,
    notes: str | None,
    tags: str | None,
) -> ImageRecord | None:
    await db.execute(update(ImageRecord).where(ImageRecord.source_key == source_key).values(notes=notes, tags=tags))
    await db.commit()
    return await get_image_by_key(db, source_key)


# ── Users ──────────────────────────────────────────────────────────────────────


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.scalars(select(User).order_by(User.created_at))
    return list(result)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(User.username == username))


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id))


async def create_user(db: AsyncSession, username: str, password_hash: str, is_admin: bool = False) -> User:
    user = User(username=username, password_hash=password_hash, is_admin=is_admin)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_active(db: AsyncSession, user: User, is_active: bool) -> User:
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True


# ── Presets ───────────────────────────────────────────────────────────────────


async def list_presets(db: AsyncSession) -> list[Preset]:
    return list(await db.scalars(select(Preset).order_by(Preset.id)))


async def get_preset(db: AsyncSession, preset_id: int) -> Preset | None:
    return await db.get(Preset, preset_id)


async def get_default_preset(db: AsyncSession) -> Preset | None:
    return await db.scalar(select(Preset).where(Preset.is_default.is_(True)))


async def get_preset_by_name(db: AsyncSession, name: str) -> Preset | None:
    return await db.scalar(select(Preset).where(Preset.name == name))


async def count_presets(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Preset)) or 0


async def set_default_preset(db: AsyncSession, preset_id: int) -> None:
    """Make `preset_id` the only default (one transaction; clear first for the unique index)."""
    await db.execute(update(Preset).where(Preset.is_default.is_(True)).values(is_default=False))
    await db.execute(update(Preset).where(Preset.id == preset_id).values(is_default=True))
    await db.commit()
