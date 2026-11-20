"""Batch job execution: process every unprocessed source image under a prefix with one preset.

The job is orchestrated on the event loop; the heavy per-image work runs in worker threads
via `image_pipeline.process_key`. Stop / skip are cooperative (see `job_registry`).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

from app.config import settings
from app.core.background import spawn
from app.core.image_pipeline import Outcome, ProcessingPlan, process_key
from app.core.image_worker import register_task
from app.core.job_registry import JobState, JobStatus, get_job
from app.core.s3 import get_s3_client, iter_source_keys
from app.db.crud import get_processed_keys, is_processed, log_activity, save_batch_history, upsert_images
from app.db.session import AsyncSessionLocal
from app.services.settings_service import SettingsOut, get_runtime_settings

logger = logging.getLogger(__name__)

_LIST_CHUNK_SIZE = 500
_MAX_ATTEMPTS = 3


def launch_job(job_id: str) -> None:
    """Start `run_job` in the background on the running event loop."""
    spawn(run_job(job_id), name=f"batch-job-{job_id}")


async def run_job(job_id: str) -> None:
    """Run a registered job to completion (or until stopped)."""
    job = get_job(job_id)
    if job is None:
        logger.warning("[%s] Job vanished before it started", job_id)
        return

    job.status = JobStatus.RUNNING
    job.started_at = time.time()
    try:
        async with AsyncSessionLocal() as db:
            rs = await get_runtime_settings(db)
            await log_activity(
                db,
                event_type="batch_start",
                message=f"Batch job started with preset '{job.preset.name}' — prefix: {job.source_prefix}",
                meta={"job_id": job.job_id, "source_prefix": job.source_prefix, "preset_id": job.preset.id},
                username=job.started_by,
            )

        keys = await _collect_keys(job, rs)
        job.total = len(keys)
        logger.info("[%s] To process: %d | Skipped: %d", job_id, job.total, job.skipped)

        if keys and not job.token.cancelled:
            plan = ProcessingPlan(
                runtime=rs,
                preset=job.preset,
                output_prefix=job.output_prefix,
                overwrite_source=job.overwrite,
                max_attempts=_MAX_ATTEMPTS,
            )
            await _process_all(job, keys, plan, max(1, rs.process_concurrency))

        job.status = JobStatus.STOPPED if job.token.cancelled else JobStatus.COMPLETED
    except Exception:
        logger.exception("[%s] Job crashed", job_id)
        job.status = JobStatus.FAILED
    finally:
        job.finished_at = time.time()
        logger.info(
            "[%s] %s. processed=%d skipped=%d failed=%d duration=%.1fs",
            job_id,
            job.status.value,
            job.processed,
            job.skipped,
            job.failed,
            job.finished_at - job.started_at,
        )
        await _persist_job_history(job)


async def _collect_keys(job: JobState, rs: SettingsOut) -> list[str]:
    """List the job's prefix, upsert what was found, and return the keys still to process."""
    already_done: set[str] = set()
    if not job.overwrite:
        async with AsyncSessionLocal() as db:
            already_done = await get_processed_keys(db)

    listing = iter_source_keys(
        get_s3_client(),
        settings.s3_bucket,
        job.source_prefix,
        rs.source_matcher(),
        exclude_prefixes=(rs.output_prefix, rs.backup_prefix),
        chunk_size=_LIST_CHUNK_SIZE,
    )
    keys: list[str] = []
    while not job.token.cancelled:
        chunk = await asyncio.to_thread(next, listing, None)
        if chunk is None:
            break
        async with AsyncSessionLocal() as db:
            await upsert_images(db, chunk, rs.source_prefix, rs.group_depth)
        for key, _ in chunk:
            if key in already_done:
                job.skipped += 1
            else:
                keys.append(key)
    return keys


async def _process_all(job: JobState, keys: list[str], plan: ProcessingPlan, concurrency: int) -> None:
    """Process `keys` with at most `concurrency` images in flight; stops early when cancelled."""
    pending = iter(keys)

    async def worker() -> None:
        for key in pending:  # shared iterator: each key is taken by exactly one worker
            if job.token.cancelled:
                return
            await _process_job_image(job, key, plan)

    await asyncio.gather(*(worker() for _ in range(concurrency)))


async def _process_job_image(job: JobState, key: str, plan: ProcessingPlan) -> None:
    if not job.overwrite:
        async with AsyncSessionLocal() as db:
            if await is_processed(db, key):
                job.skipped += 1
                return

    task = register_task(key, parent=job.token)
    if task is None:
        job.skipped += 1
        job.add_error(key, "Already being processed elsewhere")
        return

    job.in_flight.append(key)
    try:
        outcome = await process_key(task, plan)
    finally:
        job.in_flight.remove(key)

    if outcome == Outcome.PROCESSED:
        job.processed += 1
        logger.info("[%s] %d/%d done: %s", job.job_id, job.processed, job.total, key)
    elif outcome == Outcome.FAILED:
        job.failed += 1
        job.add_error(key, task.error or "Failed")
    elif job.token.cancelled:
        job.add_error(key, "Aborted (job stopped)")
    else:
        job.skipped += 1
        job.add_error(key, "Skipped by user")


async def _persist_job_history(job: JobState) -> None:
    elapsed = (job.finished_at - job.started_at) if job.started_at and job.finished_at else None
    try:
        async with AsyncSessionLocal() as db:
            await save_batch_history(
                db,
                job_id=job.job_id,
                source_prefix=job.source_prefix,
                status=job.status.value,
                total=job.total,
                processed=job.processed,
                failed=job.failed,
                skipped=job.skipped,
                started_at=datetime.fromtimestamp(job.started_at, tz=UTC) if job.started_at else None,
                completed_at=datetime.now(UTC),
                elapsed_seconds=elapsed,
            )
            await log_activity(
                db,
                event_type="batch_complete",
                message=(
                    f"Batch job {job.status.value} — {job.processed} processed, "
                    f"{job.failed} failed, {job.skipped} skipped"
                ),
                meta={
                    "job_id": job.job_id,
                    "total": job.total,
                    "processed": job.processed,
                    "failed": job.failed,
                    "elapsed": round(elapsed, 1) if elapsed else None,
                },
                username=job.started_by,
            )
    except Exception:
        logger.exception("[%s] Could not persist job history", job.job_id)
