"""Batch job endpoints + Server-Sent Events progress stream. Logic lives in services/job_service.py."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import SSE_HEADERS, require_admin_for_overwrite
from app.config import settings
from app.core.auth import CurrentUser, get_current_user
from app.core.job_registry import TERMINAL_JOB_STATUSES, JobState, get_all_jobs, get_job
from app.db.session import get_db
from app.models.schema import JobError, JobResponse, StartJobRequest
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

JobId = Annotated[str, Path(min_length=1, max_length=64)]

_MAX_ERRORS_IN_RESPONSE = 50


def _job_to_response(job: JobState) -> JobResponse:
    elapsed = None
    if job.started_at:
        elapsed = round((job.finished_at or time.time()) - job.started_at, 1)
    pct = (job.processed / job.total * 100) if job.total else 0.0
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        total=job.total,
        skipped=job.skipped,
        processed=job.processed,
        failed=job.failed,
        progress_pct=round(pct, 2),
        elapsed_seconds=elapsed,
        errors=[JobError(**error) for error in job.errors[-_MAX_ERRORS_IN_RESPONSE:]],
        bucket=settings.s3_bucket,
        source_prefix=job.source_prefix,
        output_prefix=job.output_prefix,
        overwrite=job.overwrite,
        current_key=job.current_key,
        preset_id=job.preset.id,
        preset_name=job.preset.name,
    )


def _get_or_404(job_id: str) -> JobState:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/start", response_model=JobResponse, status_code=202)
async def start_job(
    body: StartJobRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> JobResponse:
    require_admin_for_overwrite(bool(body.overwrite_original), actor)
    try:
        job = await job_service.start_job(db, body, actor=actor.username)
    except job_service.JobRequestError as exc:
        raise HTTPException(400, str(exc)) from exc
    except job_service.JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_to_response(job)


@router.post("/{job_id}/stop", response_model=JobResponse)
async def stop_job_endpoint(
    job_id: JobId,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> JobResponse:
    """Stop the job; in-flight images stop at their next checkpoint."""
    try:
        job = await job_service.request_stop(db, job_id, actor=actor.username)
    except job_service.JobNotFound as exc:
        raise HTTPException(404, "Job not found") from exc
    return _job_to_response(job)


@router.post("/{job_id}/skip", response_model=JobResponse)
async def skip_image_endpoint(
    job_id: JobId,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> JobResponse:
    """Abort the job's current image (at its next checkpoint) and move on to the next one."""
    try:
        job = await job_service.request_skip(db, job_id, actor=actor.username)
    except job_service.JobNotFound as exc:
        raise HTTPException(404, "Job not found") from exc
    except job_service.JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_to_response(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job_endpoint(job_id: JobId) -> None:
    try:
        job_service.forget_job(job_id)
    except job_service.JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except job_service.JobNotFound as exc:
        raise HTTPException(404, "Job not found") from exc


@router.get("/{job_id}", response_model=JobResponse)
async def job_status(job_id: JobId) -> JobResponse:
    return _job_to_response(_get_or_404(job_id))


@router.get("/", response_model=list[JobResponse])
async def list_jobs() -> list[JobResponse]:
    return [_job_to_response(j) for j in get_all_jobs()]


@router.get("/{job_id}/stream")
async def stream_job(job_id: JobId) -> StreamingResponse:
    """SSE: one `JobResponse` per second until the job reaches a terminal state."""
    _get_or_404(job_id)

    async def event_generator() -> AsyncIterator[str]:
        while (job := get_job(job_id)) is not None:
            yield f"data: {json.dumps(_job_to_response(job).model_dump(mode='json'))}\n\n"
            if job.status in TERMINAL_JOB_STATUSES:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)
