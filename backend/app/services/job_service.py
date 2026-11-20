"""Batch job use cases behind the Jobs API."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.batch_runner import launch_job
from app.core.job_registry import (
    JobAlreadyRunning,
    JobState,
    JobStatus,
    JobStillActive,
    create_job,
    delete_job,
    get_job,
    skip_current_image,
    stop_job,
)
from app.core.rendering import EngineUnavailable, ensure_engine_available
from app.db.crud import log_activity
from app.models.schema import StartJobRequest
from app.services.preset_service import PresetConflict, PresetNotFound, resolve_preset
from app.services.settings_service import get_runtime_settings


class JobRequestError(Exception):
    """Invalid job request; the message is safe to show."""


class JobConflict(Exception):
    """The job is not in a state that allows the operation; the message is safe to show."""


class JobNotFound(Exception):
    pass


def _is_safe_prefix(prefix: str, base: str) -> bool:
    return prefix.startswith(base) and ".." not in prefix.split("/") and "//" not in prefix


async def start_job(db: AsyncSession, body: StartJobRequest, *, actor: str) -> JobState:
    """Validate the request against the runtime prefixes and launch the job in the background."""
    rs = await get_runtime_settings(db)
    source_prefix = body.source_prefix if body.source_prefix is not None else rs.source_prefix
    output_prefix = body.output_prefix or rs.output_prefix
    if not _is_safe_prefix(source_prefix, rs.source_prefix):
        raise JobRequestError("source_prefix must be inside the configured source prefix")
    if not _is_safe_prefix(output_prefix, rs.output_prefix):
        raise JobRequestError("output_prefix must be inside the configured output prefix")
    overwrite = bool(body.overwrite_original)  # admin-only, enforced by the router

    try:
        preset = await resolve_preset(db, body.preset_id)
        ensure_engine_available("preset", preset.config)
    except PresetNotFound as exc:
        raise JobRequestError("Preset not found") from exc
    except (PresetConflict, EngineUnavailable) as exc:
        raise JobRequestError(str(exc)) from exc

    try:
        job_id = create_job(source_prefix, output_prefix, overwrite, preset, started_by=actor)
    except JobAlreadyRunning as exc:
        raise JobConflict(str(exc)) from exc

    await log_activity(
        db,
        "job.start",
        f"{actor} started batch job {job_id} with preset '{preset.name}'",
        {"job_id": job_id, "source_prefix": source_prefix, "overwrite": overwrite, "preset_id": preset.id},
        username=actor,
    )
    launch_job(job_id)
    return _require_job(job_id)


def _require_job(job_id: str) -> JobState:
    job = get_job(job_id)
    if job is None:
        raise JobNotFound(job_id)
    return job


async def request_stop(db: AsyncSession, job_id: str, *, actor: str) -> JobState:
    job = _require_job(job_id)
    if stop_job(job_id):
        await log_activity(db, "job.stop", f"{actor} stopped batch job {job_id}", {"job_id": job_id}, username=actor)
    return job


async def request_skip(db: AsyncSession, job_id: str, *, actor: str) -> JobState:
    job = _require_job(job_id)
    if job.status != JobStatus.RUNNING:
        raise JobConflict("Job is not running")
    key = job.current_key
    if skip_current_image(job_id):
        await log_activity(
            db,
            "job.skip",
            f"{actor} skipped {key} in batch job {job_id}",
            {"job_id": job_id, "key": key},
            username=actor,
        )
    return job


def forget_job(job_id: str) -> None:
    """Remove a finished job from the list. Raises `JobNotFound`, or `JobConflict` while it is active."""
    try:
        deleted = delete_job(job_id)
    except JobStillActive as exc:
        raise JobConflict(str(exc)) from exc
    if not deleted:
        raise JobNotFound(job_id)
