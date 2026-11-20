"""Image use cases behind the Images API: listing, processing, abort, notes and resets.

Publishing and restoring live in `publish_service`. Every key coming from a client is
validated with `validate_source_keys` (a source image under the runtime `source_prefix`,
never under the output / backup prefixes). Blocking boto3 and Pillow work runs in worker threads.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background import spawn
from app.core.derivatives import derivative_key, render_name
from app.core.image_pipeline import Outcome, ProcessingPlan, process_key
from app.core.image_worker import ImageTask, is_processing, register_task, request_abort
from app.core.preset_config import PresetConfig
from app.core.rendering import EngineChoice, ensure_engine_available
from app.core.s3 import presign_get
from app.core.source_filters import SourceMatcher
from app.db.crud import (
    GroupScope,
    ImageListStatus,
    ImageSortField,
    count_failed_images,
    get_group_keys,
    get_images_by_keys,
    get_retryable_failed_keys,
    list_failed_images,
    list_group_images,
    list_images_grouped,
    list_review_candidates,
    log_activity,
    mark_pending_many,
    update_image_notes,
)
from app.db.models import ImageRecord
from app.db.session import AsyncSessionLocal
from app.models.schema import (
    GroupImagesPage,
    ImageGroupOut,
    ImageOut,
    PaginatedGroups,
    PaginatedImages,
    RetryFailedResult,
)
from app.services.preset_service import resolve_preset
from app.services.settings_service import SettingsOut, get_runtime_settings

logger = logging.getLogger(__name__)

AUDIT_KEYS_SAMPLE = 10
# Images returned per group by the grouped list; the rest is read with `list_group_page`.
GROUP_IMAGE_LIMIT = 50


# ── Errors ────────────────────────────────────────────────────────────────────


class ImageRequestError(Exception):
    """A client request that cannot be fulfilled; the message is safe to show."""


class InvalidImageKeys(ImageRequestError):
    """Keys that are not source images under the current source prefix."""


class ImagesNotFound(ImageRequestError):
    """Keys that are valid but unknown to the DB."""


class ImageBusy(ImageRequestError):
    """The image is in a state that does not allow the operation."""


# ── Key validation ────────────────────────────────────────────────────────────


def is_valid_source_key(key: str, rs: SettingsOut, matcher: SourceMatcher | None = None) -> bool:
    """True if `key` is a source image under `source_prefix` and outside the output/backup prefixes."""
    if not key.startswith(rs.source_prefix) or key.startswith((rs.output_prefix, rs.backup_prefix)):
        return False
    if key.startswith("/") or "\\" in key or any(ord(c) < 32 for c in key):
        return False
    if any(seg in ("", ".", "..") for seg in key.split("/")):
        return False
    return (matcher or rs.source_matcher()).matches(key)


def validate_source_keys(keys: Iterable[str], rs: SettingsOut) -> None:
    matcher = rs.source_matcher()
    invalid = [k for k in keys if not is_valid_source_key(k, rs, matcher)]
    if invalid:
        logger.info("Rejected %d invalid image key(s), e.g. %r", len(invalid), invalid[0][:200])
        raise InvalidImageKeys(f"{len(invalid)} key(s) are not source images under the configured prefix")


async def load_records(db: AsyncSession, keys: Sequence[str]) -> list[ImageRecord]:
    """Records for `keys` (deduplicated, request order kept). Raises if any key is unknown."""
    unique = list(dict.fromkeys(keys))
    records = {r.source_key: r for r in await get_images_by_keys(db, unique)}
    missing = [k for k in unique if k not in records]
    if missing:
        raise ImagesNotFound(f"{len(missing)} image(s) not found")
    return [records[k] for k in unique]


async def validated_records(db: AsyncSession, keys: Sequence[str]) -> tuple[SettingsOut, list[ImageRecord]]:
    rs = await get_runtime_settings(db)
    validate_source_keys(keys, rs)
    return rs, await load_records(db, keys)


def backup_key_for(source_key: str, backup_prefix: str) -> str:
    return f"{backup_prefix}{source_key}"


# ── Presentation ──────────────────────────────────────────────────────────────


def _enrich(record: ImageRecord, rs: SettingsOut) -> ImageOut:
    expires = rs.presign_expires_seconds
    out = ImageOut.model_validate(record)
    out.source_url = presign_get(record.source_key, expires)
    out.processed_url = presign_get(record.processed_key, expires)
    if record.is_published:
        backup_key = record.backup_key or backup_key_for(record.source_key, rs.backup_prefix)
        out.backup_url = presign_get(backup_key, expires)
        for spec in rs.publish.derivatives:
            url = presign_get(derivative_key(record.source_key, spec), expires)
            if url:
                out.derivative_urls[render_name(spec.name, record.source_key)] = url
    out.is_processing = is_processing(record.source_key)
    return out


async def enrich_records(records: Sequence[ImageRecord], rs: SettingsOut) -> list[ImageOut]:
    """Attach presigned URLs and live processing state (signing runs off the event loop)."""
    return await asyncio.to_thread(lambda: [_enrich(r, rs) for r in records])


def _total_pages(total: int, page_size: int) -> int:
    return max(1, -(-total // page_size))


async def list_image_groups(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: ImageListStatus | None,
    search: str | None,
    sort_by: ImageSortField,
    sort_order: str,
) -> PaginatedGroups:
    """One page of groups, each with its first `GROUP_IMAGE_LIMIT` images and its real size.

    With `group_depth` 0 it is one ungrouped page of `page_size` images.
    """
    rs = await get_runtime_settings(db)
    grouped = rs.group_depth > 0
    result = await list_images_grouped(
        db,
        page=page,
        page_size=page_size,
        grouped=grouped,
        per_group=GROUP_IMAGE_LIMIT,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order="asc" if sort_order == "asc" else "desc",
    )
    records = [r for g in result.groups for r in g.images]
    enriched = dict(zip((r.id for r in records), await enrich_records(records, rs), strict=True))
    return PaginatedGroups(
        items=[
            ImageGroupOut(
                group=g.group,
                images=[enriched[r.id] for r in g.images],
                image_count=g.image_count,
                publishable_count=g.publishable_count,
            )
            for g in result.groups
        ],
        grouped=grouped,
        total_images=result.total_images,
        total_groups=result.total_groups,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(result.total_groups if grouped else result.total_images, page_size),
    )


async def list_group_page(
    db: AsyncSession, scope: GroupScope, *, offset: int, limit: int, sort_by: ImageSortField, sort_order: str
) -> GroupImagesPage:
    """More images of one group, in the order of the grouped list."""
    rs = await get_runtime_settings(db)
    records, total = await list_group_images(
        db, scope, offset=offset, limit=limit, sort_by=sort_by, sort_order="asc" if sort_order == "asc" else "desc"
    )
    return GroupImagesPage(
        group=scope.group, items=await enrich_records(records, rs), total=total, offset=offset, limit=limit
    )


async def list_review(db: AsyncSession, *, page: int, page_size: int, search: str | None) -> PaginatedImages:
    """One page of the processed images that are not published yet."""
    rs = await get_runtime_settings(db)
    found = await list_review_candidates(db, page=page, page_size=page_size, search=search)
    return PaginatedImages(
        items=await enrich_records(found.records, rs),
        total=found.total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(found.total, page_size),
    )


async def list_failed(db: AsyncSession, *, page: int, page_size: int, search: str | None) -> PaginatedImages:
    rs = await get_runtime_settings(db)
    found = await list_failed_images(db, page=page, page_size=page_size, search=search)
    return PaginatedImages(
        items=await enrich_records(found.records, rs),
        total=found.total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(found.total, page_size),
    )


# ── Processing ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QueueResult:
    queued: int
    already_processing: list[str]
    preset_id: int


def _register(keys: Iterable[str]) -> tuple[list[ImageTask], list[str]]:
    tasks: list[ImageTask] = []
    busy: list[str] = []
    for key in keys:
        task = register_task(key)
        if task is None:
            busy.append(key)
        else:
            tasks.append(task)
    return tasks, busy


def _uses_ai_for_every_image(engine: EngineChoice, config: PresetConfig) -> bool:
    if engine in ("openai", "gemini"):
        return True
    return engine == "preset" and config.ai.engine != "none" and config.ai.below_px == 0


async def _run_tasks(tasks: list[ImageTask], plan: ProcessingPlan, concurrency: int, actor: str) -> None:
    outcomes: Counter[Outcome] = Counter()
    queue = iter(tasks)

    async def _worker() -> None:  # a few workers over one iterator: no coroutine per queued image
        for task in queue:
            outcomes[await process_key(task, plan)] += 1

    await asyncio.gather(*(_worker() for _ in range(max(1, min(concurrency, len(tasks))))))
    done, failed, aborted = (outcomes[o] for o in (Outcome.PROCESSED, Outcome.FAILED, Outcome.ABORTED))
    total = len(tasks)
    meta: dict[str, Any] = {
        "total": total,
        "done": done,
        "failed": failed,
        "aborted": aborted,
        "preset_id": plan.preset.id,
        "engine": plan.engine,
    }
    message = f"Processed {done}/{total} image{'s' if total != 1 else ''} with preset '{plan.preset.name}'"
    async with AsyncSessionLocal() as db:
        await log_activity(db, "process", message + (f" — {failed} failed" if failed else ""), meta, username=actor)


async def _queue(
    db: AsyncSession,
    rs: SettingsOut,
    keys: Iterable[str],
    *,
    actor: str,
    preset_id: int | None,
    engine: EngineChoice,
    prompt: str | None,
    replace: bool,
    audit: dict[str, Any] | None = None,
) -> QueueResult:
    """Claim `keys` (already validated) and process them in the background."""
    preset = await resolve_preset(db, preset_id)
    ensure_engine_available(engine, preset.config)
    tasks, busy = _register(keys)
    if not tasks:
        return QueueResult(0, busy, preset.id)

    plan = ProcessingPlan(runtime=rs, preset=preset, engine=engine, prompt=prompt, overwrite_source=replace)
    ai_only = _uses_ai_for_every_image(engine, preset.config)
    concurrency = rs.ai_concurrency if ai_only else rs.process_concurrency
    spawn(_run_tasks(tasks, plan, concurrency, actor), name=f"process-{preset.id}-{engine}")

    await log_activity(
        db,
        "image.process",
        f"{actor} queued {len(tasks)} image(s) with preset '{preset.name}'"
        + ("" if engine == "preset" else f" (engine: {engine})"),
        {
            "keys": [t.source_key for t in tasks[:AUDIT_KEYS_SAMPLE]],
            "preset_id": preset.id,
            "engine": engine,
            "replace": replace,
            **(audit or {}),
        },
        username=actor,
    )
    return QueueResult(len(tasks), busy, preset.id)


async def queue_processing(
    db: AsyncSession,
    keys: Sequence[str],
    *,
    actor: str,
    preset_id: int | None = None,
    engine: EngineChoice = "preset",
    prompt: str | None = None,
    replace: bool = False,
) -> QueueResult:
    """Validate keys and preset, claim the images, and process them in the background.

    Raises `PresetNotFound` / `EngineUnavailable` besides the `ImageRequestError` family.
    """
    rs, records = await validated_records(db, keys)
    return await _queue(
        db,
        rs,
        (r.source_key for r in records),
        actor=actor,
        preset_id=preset_id,
        engine=engine,
        prompt=prompt,
        replace=replace,
    )


async def queue_group_processing(
    db: AsyncSession,
    scope: GroupScope,
    *,
    actor: str,
    preset_id: int | None = None,
    engine: EngineChoice = "preset",
    prompt: str | None = None,
    replace: bool = False,
) -> QueueResult:
    """`queue_processing` for every image of one group: the keys come from the DB, not the client."""
    rs = await get_runtime_settings(db)
    matcher = rs.source_matcher()
    keys = [k for k in await get_group_keys(db, scope) if is_valid_source_key(k, rs, matcher)]
    if not keys:
        raise ImagesNotFound("No images in this group")
    return await _queue(
        db,
        rs,
        keys,
        actor=actor,
        preset_id=preset_id,
        engine=engine,
        prompt=prompt,
        replace=replace,
        audit={"group": scope.group},
    )


async def retry_failed(
    db: AsyncSession, *, actor: str, replace: bool, max_retries: int | None, preset_id: int | None
) -> RetryFailedResult:
    """Requeue failed (not user-aborted) images that are below the retry limit.

    The result says why the rest was left alone: at the limit, or below it but busy / not a source.
    """
    rs = await get_runtime_settings(db)
    preset = await resolve_preset(db, preset_id)
    ensure_engine_available("preset", preset.config)
    limit = rs.max_retry_count if max_retries is None else max_retries
    total_failed = await count_failed_images(db)
    matcher = rs.source_matcher()
    below_limit = await get_retryable_failed_keys(db, limit)
    eligible = [key for key in below_limit if is_valid_source_key(key, rs, matcher) and not is_processing(key)]
    tasks, _ = _register(eligible)
    if tasks:
        plan = ProcessingPlan(runtime=rs, preset=preset, overwrite_source=replace)
        spawn(_run_tasks(tasks, plan, rs.process_concurrency, actor), name="retry-failed")
        await log_activity(
            db,
            "image.retry_failed",
            f"{actor} requeued {len(tasks)} failed image(s) with preset '{preset.name}'",
            {"keys": [t.source_key for t in tasks][:AUDIT_KEYS_SAMPLE], "preset_id": preset.id},
            username=actor,
        )
    return RetryFailedResult(
        queued=len(tasks),
        skipped_max_retries=max(0, total_failed - len(below_limit)),
        skipped_other=len(below_limit) - len(tasks),
    )


async def abort_processing(db: AsyncSession, key: str, *, actor: str) -> None:
    """Request a cooperative abort; it takes effect at the image's next checkpoint."""
    rs = await get_runtime_settings(db)
    validate_source_keys([key], rs)
    if not request_abort(key):
        raise ImageBusy("Image is not currently being processed")
    await log_activity(db, "image.abort", f"{actor} aborted processing of {key}", {"key": key}, username=actor)


async def reset_to_pending(db: AsyncSession, keys: Sequence[str], *, actor: str) -> int:
    """DB-only reset to pending; images that are processing, published or hold a backup are left alone.

    (An image with a backup needs a real restore: its source may already have been overwritten.)
    """
    _, records = await validated_records(db, keys)
    resettable = [
        r.source_key for r in records if not is_processing(r.source_key) and not r.is_published and r.backup_key is None
    ]
    count = await mark_pending_many(db, resettable)
    await log_activity(
        db,
        "image.reset_pending",
        f"{actor} reset {count} image(s) to pending",
        {"keys": resettable[:AUDIT_KEYS_SAMPLE]},
        username=actor,
    )
    return count


async def update_notes(db: AsyncSession, key: str, notes: str | None, tags: str | None, *, actor: str) -> ImageRecord:
    await validated_records(db, [key])
    record = await update_image_notes(db, key, notes, tags)
    if record is None:
        raise ImagesNotFound("Image not found")
    await log_activity(db, "image.notes", f"{actor} updated notes for {key}", {"key": key}, username=actor)
    return record
