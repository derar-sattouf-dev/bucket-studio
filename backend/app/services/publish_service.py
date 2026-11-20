"""Publish processed images in place, and roll them back.

Publish (per image):
    1. download the processed output and render the configured derivatives in memory
       (nothing in the bucket changes if the output is missing or broken);
    2. copy the original to `<backup_prefix><source_key>` (private, no public ACL) and record that
       location on the image (`backup_key`) *before* anything is overwritten;
    3. copy the processed bytes over the source key as-is (no re-render);
    4. upload the derivatives next to the source.
The processed output must have the source's format: the key (and its extension) does not change.

The original is never lost:
    * an image that is already published is refused;
    * one image is published or restored by one request at a time (`_claim`), and its state is
      re-read inside the claim, so overlapping requests cannot both pass the check;
    * once `backup_key` is set the backup is not written again, so retrying a publish that failed
      after the overwrite (a derivative upload, the final commit) cannot replace the original
      with the processed image.

Restore (per image):
    * has a backup (published, or a publish that failed half-way): the backup is copied back over
      the source and the derivatives are **regenerated from the restored original**. Deleting them
      instead could break pages that link to derivative files which existed before publishing;
      regenerating never removes a file.
    * processed, source untouched: the processed output is deleted (no bucket change otherwise).
    Either way the image goes back to pending.

Bulk publish ("publish all", or every publishable image of one group) runs as one background
task at a time: the request only starts it and `bulk_publish_status` reports its progress.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.background import spawn
from app.core.derivatives import RenderedDerivative, render_all
from app.core.image_pipeline import describe_error, public_error
from app.core.image_worker import is_processing
from app.core.imaging import CONTENT_TYPES, ImageFormat, extension_of, format_of_extension, probe
from app.core.s3 import CACHE_MUTABLE, copy_object, delete_object, download_bytes, get_s3_client, put_image
from app.db.crud import (
    GroupScope,
    get_image_by_key,
    get_review_candidate_keys,
    log_activity,
    mark_pending_many,
    mark_published,
    set_backup_key,
)
from app.db.models import ImageRecord
from app.db.session import AsyncSessionLocal
from app.services.image_service import AUDIT_KEYS_SAMPLE, backup_key_for, is_valid_source_key, validated_records
from app.services.settings_service import SettingsOut, get_runtime_settings

logger = logging.getLogger(__name__)

_PUBLISH_CONCURRENCY = 4
_MAX_BULK_ERRORS = 100


class PublishRefused(Exception):
    """The image cannot be published as it is; the message is safe to show."""


def _source_format(source_key: str) -> ImageFormat:
    fmt = format_of_extension(extension_of(source_key))
    if fmt is None:
        raise PublishRefused("The source file type is not supported")
    return fmt


def _error(key: str, message: str) -> dict[str, Any]:
    return {"key": key, "status": "error", "error": message}


# ── One operation per image at a time ─────────────────────────────────────────

# Keys being published or restored right now. In-memory is enough: the backend is one process.
_in_flight: set[str] = set()

_BUSY = "Image is already being published or restored"


@contextmanager
def _claim(key: str) -> Iterator[bool]:
    """Yield True if this caller now owns `key`, False if another publish/restore holds it."""
    if key in _in_flight:
        yield False
        return
    _in_flight.add(key)
    try:
        yield True
    finally:
        _in_flight.discard(key)


async def _fresh(key: str) -> ImageRecord | None:
    """The image's current row (the caller's copy may predate another request's publish)."""
    async with AsyncSessionLocal() as db:
        return await get_image_by_key(db, key)


# ── Publish ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Prepared:
    data: bytes
    fmt: ImageFormat
    derivatives: list[RenderedDerivative]


def _prepare_sync(source_key: str, processed_key: str, rs: SettingsOut) -> _Prepared:
    """Download and check the processed output and render the derivatives; the bucket is not changed."""
    fmt = _source_format(source_key)
    data = download_bytes(get_s3_client(), settings.s3_bucket, processed_key)
    actual, _, _ = probe(data)
    if actual != fmt:
        raise PublishRefused(f"The processed output is {actual or 'unknown'}, but the source is {fmt}")
    return _Prepared(data, fmt, render_all(data, rs.publish, source_key, fmt))


def _backup_sync(source_key: str, backup_key: str) -> None:
    copy_object(get_s3_client(), settings.s3_bucket, source_key, backup_key)  # no ACL: backups stay private


def _overwrite_sync(source_key: str, prepared: _Prepared, rs: SettingsOut) -> None:
    s3, bucket = get_s3_client(), settings.s3_bucket
    put_image(
        s3,
        bucket,
        source_key,
        prepared.data,
        CONTENT_TYPES[prepared.fmt],
        acl=rs.s3_object_acl,
        cache_control=CACHE_MUTABLE,
    )
    for derivative in prepared.derivatives:
        put_image(s3, bucket, derivative.key, derivative.data, derivative.content_type, acl=rs.s3_object_acl)


async def _publish_claimed(key: str, rs: SettingsOut, actor: str, log_each: bool) -> dict[str, Any]:
    record = await _fresh(key)
    if record is None:
        return _error(key, "Image not found")
    if is_processing(key):
        return _error(key, "Image is currently being processed")
    if record.is_published:
        return _error(key, "Image is already published; restore it first")
    if not record.processed_key or record.processed_key == key:
        return _error(key, "No processed output to publish")
    if format_of_extension(extension_of(record.processed_key)) != format_of_extension(extension_of(key)):
        return _error(key, "The processed output has a different format than the source; use a 'keep' preset")

    prepared = await asyncio.to_thread(_prepare_sync, key, record.processed_key, rs)

    # A backup recorded by an earlier attempt already holds the original: the source may since have
    # been overwritten, so copying it again would destroy that original.
    backup_key = record.backup_key
    if backup_key is None:
        backup_key = backup_key_for(key, rs.backup_prefix)
        await asyncio.to_thread(_backup_sync, key, backup_key)
        async with AsyncSessionLocal() as db:
            await set_backup_key(db, key, backup_key)

    await asyncio.to_thread(_overwrite_sync, key, prepared, rs)
    size = len(prepared.data)
    async with AsyncSessionLocal() as db:
        await mark_published(db, key, size)
        if log_each:
            await log_activity(
                db, "publish", f"Published {key}", {"key": key, "size_kb": round(size / 1024, 1)}, username=actor
            )
    return {"key": key, "status": "published", "backup": backup_key, "size": size}


async def _publish_one(key: str, rs: SettingsOut, actor: str, *, log_each: bool = True) -> dict[str, Any]:
    """Publish one image. `log_each=False` skips its activity entry (bulk runs write one summary)."""
    with _claim(key) as claimed:
        if not claimed:
            return _error(key, _BUSY)
        try:
            return await _publish_claimed(key, rs, actor, log_each)
        except PublishRefused as exc:
            return _error(key, str(exc))
        except Exception as exc:
            logger.error("Publish failed for %s: %s", key, describe_error(exc), exc_info=True)
            return _error(key, public_error(exc))


async def _publish_records(records: Sequence[ImageRecord], rs: SettingsOut, actor: str) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(_PUBLISH_CONCURRENCY)

    async def _bounded(record: ImageRecord) -> dict[str, Any]:
        async with sem:
            return await _publish_one(record.source_key, rs, actor)

    return list(await asyncio.gather(*(_bounded(r) for r in records)))


async def publish_images(db: AsyncSession, keys: Sequence[str], *, actor: str) -> list[dict[str, Any]]:
    rs, records = await validated_records(db, keys)
    results = await _publish_records(records, rs, actor)
    await log_activity(
        db,
        "image.publish",
        f"{actor} published {sum(r['status'] == 'published' for r in results)}/{len(records)} image(s)",
        {"keys": [r.source_key for r in records][:AUDIT_KEYS_SAMPLE]},
        username=actor,
    )
    return results


# ── Bulk publish (background) ─────────────────────────────────────────────────


class BulkPublishRunning(Exception):
    """A bulk publish is already in progress."""


@dataclass
class BulkPublishState:
    """Progress of the current (or last) bulk publish. In-memory: the backend is one process."""

    running: bool = False
    total: int = 0
    done: int = 0
    published: int = 0
    failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    errors: list[dict[str, str]] = field(default_factory=list)  # the first `_MAX_BULK_ERRORS` only


_bulk = BulkPublishState()


def bulk_publish_status() -> BulkPublishState:
    return _bulk


async def _run_bulk_publish(state: BulkPublishState, keys: list[str], rs: SettingsOut, actor: str, what: str) -> None:
    queue = iter(keys)

    async def _worker() -> None:  # counters only: no per-image result is kept
        for key in queue:
            result = await _publish_one(key, rs, actor, log_each=False)
            state.done += 1
            if result["status"] == "published":
                state.published += 1
                continue
            state.failed += 1
            if len(state.errors) < _MAX_BULK_ERRORS:
                state.errors.append({"key": key, "error": str(result.get("error", "Publish failed"))})

    try:
        await asyncio.gather(*(_worker() for _ in range(_PUBLISH_CONCURRENCY)))
    finally:
        state.running = False
        state.finished_at = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            await log_activity(
                db,
                "image.publish_all",
                f"{actor} published {state.published}/{state.total} {what}"
                + (f" ({state.failed} failed)" if state.failed else ""),
                {"total": state.total, "published": state.published, "failed": state.failed},
                username=actor,
            )


async def start_bulk_publish(db: AsyncSession, *, actor: str, scope: GroupScope | None = None) -> int:
    """Publish every processed, unpublished image (of one group, with `scope`) in the background.

    Returns how many images the run covers; raises `BulkPublishRunning` if one is in progress.
    """
    global _bulk
    if _bulk.running:
        raise BulkPublishRunning
    # Claimed before the first await, so two overlapping requests cannot both start a run.
    state = _bulk = BulkPublishState(running=True, started_at=datetime.now(UTC))
    try:
        rs = await get_runtime_settings(db)
        matcher = rs.source_matcher()
        keys = [k for k in await get_review_candidate_keys(db, scope) if is_valid_source_key(k, rs, matcher)]
    except BaseException:
        state.running = False
        state.finished_at = datetime.now(UTC)
        raise
    state.total = len(keys)
    if not keys:
        state.running = False
        state.finished_at = datetime.now(UTC)
        return 0
    what = "processed image(s)" if scope is None else f"processed image(s) of group '{scope.group or 'Ungrouped'}'"
    spawn(_run_bulk_publish(state, keys, rs, actor, what), name="publish-all")
    return len(keys)


# ── Restore ───────────────────────────────────────────────────────────────────


def _restore_published_sync(source_key: str, backup_key: str, rs: SettingsOut) -> None:
    """Copy the backup over the source and regenerate the derivatives from it."""
    s3, bucket = get_s3_client(), settings.s3_bucket
    original = download_bytes(s3, bucket, backup_key)
    derivatives = render_all(original, rs.publish, source_key, _source_format(source_key))
    copy_object(s3, bucket, backup_key, source_key, acl=rs.s3_object_acl)
    for derivative in derivatives:
        put_image(s3, bucket, derivative.key, derivative.data, derivative.content_type, acl=rs.s3_object_acl)


def _delete_quietly(key: str) -> None:
    try:
        delete_object(get_s3_client(), settings.s3_bucket, key)
    except Exception as exc:
        logger.warning("Could not delete %s: %s", key, type(exc).__name__)


async def _restore_claimed(key: str, rs: SettingsOut, actor: str) -> dict[str, Any]:
    record = await _fresh(key)
    if record is None:
        return _error(key, "Image not found")
    if is_processing(key):
        return _error(key, "Image is currently being processed")

    # `backup_key` without `is_published` is a publish that failed after the backup was taken: the
    # source may already hold the processed image, so the original has to come back from the backup.
    has_backup = record.is_published or record.backup_key is not None
    if has_backup:
        # Images published before `backup_key` existed keep their backup under the configured prefix.
        backup_key = record.backup_key or backup_key_for(key, rs.backup_prefix)
        await asyncio.to_thread(_restore_published_sync, key, backup_key, rs)
        entry: dict[str, Any] = {"key": key, "status": "restored", "from": backup_key}
    else:
        entry = {"key": key, "status": "reset"}
    if record.processed_key and record.processed_key != key:
        await asyncio.to_thread(_delete_quietly, record.processed_key)

    async with AsyncSessionLocal() as db:
        await mark_pending_many(db, [key])
        await log_activity(db, "restore", f"Restored {key}", {"key": key, "was_published": has_backup}, username=actor)
    return entry


async def _restore_one(record: ImageRecord, rs: SettingsOut, actor: str) -> dict[str, Any]:
    key = record.source_key
    with _claim(key) as claimed:
        if not claimed:
            return _error(key, _BUSY)
        try:
            return await _restore_claimed(key, rs, actor)
        except PublishRefused as exc:
            return _error(key, str(exc))
        except Exception as exc:
            logger.error("Restore failed for %s: %s", key, describe_error(exc), exc_info=True)
            return _error(key, public_error(exc))


async def restore_images(db: AsyncSession, keys: Sequence[str], *, actor: str) -> list[dict[str, Any]]:
    """Undo a publish (backup → source) or discard an unpublished processed output."""
    rs, records = await validated_records(db, keys)
    sem = asyncio.Semaphore(_PUBLISH_CONCURRENCY)

    async def _bounded(record: ImageRecord) -> dict[str, Any]:
        async with sem:
            return await _restore_one(record, rs, actor)

    results = list(await asyncio.gather(*(_bounded(r) for r in records)))
    await log_activity(
        db,
        "image.restore",
        f"{actor} restored {len(records)} image(s)",
        {"keys": [r.source_key for r in records][:AUDIT_KEYS_SAMPLE]},
        username=actor,
    )
    return results
