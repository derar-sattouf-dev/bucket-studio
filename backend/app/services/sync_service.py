"""S3 → DB sync. Single implementation used by the manual endpoint and the scheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from app.config import settings
from app.core.batch_runner import launch_job
from app.core.cancellation import CancelToken
from app.core.job_registry import JobAlreadyRunning, create_job, get_running_job
from app.core.s3 import get_s3_client, iter_source_keys
from app.db.crud import log_activity, upsert_images
from app.db.session import AsyncSessionLocal
from app.services.preset_service import PresetConflict, PresetNotFound, resolve_preset
from app.services.settings_service import get_runtime_settings

logger = logging.getLogger(__name__)

SyncTrigger = Literal["manual", "auto"]

_LIST_CHUNK_SIZE = 200
_lock = asyncio.Lock()
_current_token: CancelToken | None = None


class SyncUnavailable(Exception):
    """A sync cannot start right now (another sync or a batch job is running)."""


@dataclass(frozen=True)
class SyncResult:
    new_images: int
    cancelled: bool
    auto_job_id: str | None


def is_sync_running() -> bool:
    return _lock.locked()


def request_sync_cancel() -> bool:
    """Ask the running sync to stop after the current page. False if none is running."""
    token = _current_token
    if token is None:
        return False
    token.cancel("Sync cancelled by user")
    return True


async def cancel_sync(actor: str) -> bool:
    """Cancel the running sync and record who did it."""
    if not request_sync_cancel():
        return False
    async with AsyncSessionLocal() as db:
        await log_activity(db, "sync.cancel", f"{actor} cancelled the running sync", username=actor)
    return True


async def sync_bucket(trigger: SyncTrigger, actor: str | None = None) -> SyncResult:
    """Insert every new source image under the runtime `source_prefix` as pending.

    Optionally starts a batch job afterwards (`auto_process_after_sync`).
    Raises `SyncUnavailable` if a sync or batch job is already running.
    """
    global _current_token
    if get_running_job() is not None:
        raise SyncUnavailable("A batch job is running — sync is blocked to avoid conflicts")
    if _lock.locked():
        raise SyncUnavailable("A sync is already in progress")

    async with _lock:
        token = _current_token = CancelToken()
        try:
            async with AsyncSessionLocal() as db:
                rs = await get_runtime_settings(db)

            listing = iter_source_keys(
                get_s3_client(),
                settings.s3_bucket,
                rs.source_prefix,
                rs.source_matcher(),
                exclude_prefixes=(rs.output_prefix, rs.backup_prefix),
                chunk_size=_LIST_CHUNK_SIZE,
            )
            total_new = 0
            while not token.cancelled:
                chunk = await asyncio.to_thread(next, listing, None)
                if chunk is None:
                    break
                async with AsyncSessionLocal() as db:
                    total_new += await upsert_images(db, chunk, rs.source_prefix, rs.group_depth)
        finally:
            _current_token = None

    cancelled = token.cancelled
    if cancelled:
        logger.info("[sync] Cancelled by user after %d new image(s)", total_new)

    if trigger == "manual" or total_new:
        label = "Manual sync" if trigger == "manual" else "Auto-sync"
        plural = "s" if total_new != 1 else ""
        suffix = " (cancelled)" if cancelled else ""
        async with AsyncSessionLocal() as db:
            await log_activity(
                db,
                "sync",
                f"{label}: {total_new} new image{plural} discovered{suffix}",
                {"total_new": total_new, "auto": trigger == "auto", "cancelled": cancelled},
                username=actor,
            )

    auto_job_id = None
    if total_new and not cancelled and rs.auto_process_after_sync and get_running_job() is None:
        try:
            async with AsyncSessionLocal() as db:
                preset = await resolve_preset(db, None)
            auto_job_id = create_job(rs.source_prefix, rs.output_prefix, False, preset, started_by=actor)
        except (JobAlreadyRunning, PresetNotFound, PresetConflict) as exc:
            logger.warning("[sync] Could not auto-start batch: %s", exc)
        else:
            launch_job(auto_job_id)
            logger.info("[sync] Auto-process started — job_id=%s", auto_job_id)

    return SyncResult(new_images=total_new, cancelled=cancelled, auto_job_id=auto_job_id)
