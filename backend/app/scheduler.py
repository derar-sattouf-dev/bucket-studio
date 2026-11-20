"""Periodic S3 auto-sync (APScheduler on the application's event loop).

The scheduled job calls the same `sync_bucket` as `POST /images/sync`; it is skipped while
a batch job or another sync is running.
"""

from __future__ import annotations

import logging

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.sync_service import SyncUnavailable, sync_bucket

logger = logging.getLogger(__name__)

_JOB_ID = "auto_sync"
_scheduler = AsyncIOScheduler()


async def _sync_job() -> None:
    try:
        result = await sync_bucket("auto")
    except SyncUnavailable as exc:
        logger.info("[scheduler] Skipping auto-sync: %s", exc)
    except Exception:
        logger.exception("[scheduler] Auto-sync failed")
    else:
        logger.info("[scheduler] Auto-sync complete — %d new image(s)", result.new_images)


def reschedule_sync(minutes: int) -> None:
    """Apply a new sync interval live; `minutes <= 0` disables auto-sync."""
    if minutes <= 0:
        try:
            _scheduler.remove_job(_JOB_ID)
            logger.info("[scheduler] Auto-sync disabled")
        except JobLookupError:
            pass
        return

    _scheduler.add_job(
        _sync_job,
        trigger="interval",
        minutes=minutes,
        id=_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("[scheduler] Auto-sync scheduled every %d min", minutes)


def start_scheduler(minutes: int | None = None) -> None:
    """Start the scheduler (call from within the running event loop)."""
    interval = minutes if minutes is not None else settings.sync_interval_minutes
    reschedule_sync(interval)
    if interval <= 0:
        logger.info("[scheduler] Auto-sync disabled (sync_interval_minutes=0)")
    if not _scheduler.running:
        _scheduler.start()


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[shutdown] Scheduler stopped")
