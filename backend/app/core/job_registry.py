"""In-memory registry for batch processing jobs (single-process state).

A job owns a `CancelToken`; every image processed by the job gets a child token in
`image_worker`, so stopping the job cancels all of its in-flight images at their next
checkpoint, and skipping cancels just the job's current image.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.core.cancellation import CancelToken
from app.core.image_worker import request_abort
from app.core.preset_config import ResolvedPreset

logger = logging.getLogger(__name__)

_MAX_JOB_ERRORS = 500
_FINISHED_JOB_TTL_SECONDS = 3600


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_JOB_STATUSES = frozenset({JobStatus.STOPPED, JobStatus.COMPLETED, JobStatus.FAILED})
_ACTIVE_JOB_STATUSES = frozenset({JobStatus.PENDING, JobStatus.RUNNING})


class JobRegistryError(Exception):
    """The registry refused an operation; the message is safe to show."""


class JobAlreadyRunning(JobRegistryError):
    """Only one job runs at a time."""


class JobStillActive(JobRegistryError):
    """A pending or running job cannot be deleted."""


@dataclass
class JobState:
    job_id: str
    source_prefix: str
    output_prefix: str
    overwrite: bool
    preset: ResolvedPreset
    started_by: str | None = None
    status: JobStatus = JobStatus.PENDING
    total: int = 0
    skipped: int = 0
    processed: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    token: CancelToken = field(default_factory=CancelToken)
    in_flight: list[str] = field(default_factory=list)

    @property
    def current_key(self) -> str | None:
        """The longest-running in-flight image (the one `skip` acts on)."""
        return self.in_flight[0] if self.in_flight else None

    def add_error(self, key: str, error: str) -> None:
        if len(self.errors) < _MAX_JOB_ERRORS:
            self.errors.append({"key": key, "error": error})


# `_lock` guards the `_jobs` dict itself (jobs are registered and deleted from request handlers,
# and read from them too). The fields of one `JobState` are only written on the event loop.
_jobs: dict[str, JobState] = {}
_lock = threading.Lock()


def create_job(
    source_prefix: str,
    output_prefix: str,
    overwrite: bool,
    preset: ResolvedPreset,
    started_by: str | None = None,
) -> str:
    """Register a new job. Raises `JobAlreadyRunning` if another job is still active."""
    with _lock:
        if any(j.status in _ACTIVE_JOB_STATUSES for j in _jobs.values()):
            raise JobAlreadyRunning("A job is already running. Stop it before starting a new one.")
        cutoff = time.time() - _FINISHED_JOB_TTL_SECONDS
        stale = [jid for jid, j in _jobs.items() if j.status in TERMINAL_JOB_STATUSES and (j.finished_at or 0) < cutoff]
        for jid in stale:
            del _jobs[jid]
        job_id = str(uuid.uuid4())
        _jobs[job_id] = JobState(
            job_id=job_id,
            source_prefix=source_prefix,
            output_prefix=output_prefix,
            overwrite=overwrite,
            preset=preset,
            started_by=started_by,
        )
        return job_id


def get_job(job_id: str) -> JobState | None:
    with _lock:
        return _jobs.get(job_id)


def delete_job(job_id: str) -> bool:
    """Forget a finished job. Raises `JobStillActive` if it has not finished."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return False
        if job.status not in TERMINAL_JOB_STATUSES:
            raise JobStillActive("Cannot delete a running job. Stop it first.")
        del _jobs[job_id]
        return True


def stop_job(job_id: str) -> bool:
    """Request the job to stop; in-flight images unwind at their next checkpoint."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job.status not in _ACTIVE_JOB_STATUSES:
            return False
    job.token.cancel("Job stopped by user")
    logger.info("[%s] Stop requested", job_id)
    return True


def skip_current_image(job_id: str) -> bool:
    """Cancel the job's current image; the job moves on to the next one."""
    with _lock:
        job = _jobs.get(job_id)
        key = job.current_key if job is not None and job.status == JobStatus.RUNNING else None
    if key is None:
        return False
    logger.info("[%s] Skip requested for %s", job_id, key)
    return request_abort(key)


def get_all_jobs() -> list[JobState]:
    with _lock:
        jobs = list(_jobs.values())
    return sorted(jobs, key=lambda j: j.started_at or 0, reverse=True)


def get_running_job() -> JobState | None:
    """The active (pending or running) job, if any."""
    with _lock:
        return next((job for job in _jobs.values() if job.status in _ACTIVE_JOB_STATUSES), None)
