"""In-memory registry of images currently being processed (single-process state).

Each registered image owns a `CancelToken`. Aborting an image only sets that token; the
worker notices at its next checkpoint and reports the final status via `finish_task`.
Both the Images page and batch jobs register here, so `is_processing` and abort work
the same regardless of who started the work.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import StrEnum

from app.core.cancellation import CancelToken

logger = logging.getLogger(__name__)

_MAX_FINISHED_TASKS = 500


class TaskStatus(StrEnum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class ImageTask:
    source_key: str
    token: CancelToken
    status: TaskStatus = TaskStatus.PROCESSING
    error: str | None = None


_tasks: dict[str, ImageTask] = {}
_lock = threading.Lock()


def _prune_finished() -> None:
    finished = [k for k, t in _tasks.items() if t.status != TaskStatus.PROCESSING]
    if len(finished) > _MAX_FINISHED_TASKS:
        for key in finished[: len(finished) - _MAX_FINISHED_TASKS]:
            del _tasks[key]


def register_task(source_key: str, parent: CancelToken | None = None) -> ImageTask | None:
    """Claim `source_key` for processing. Returns None if it is already being processed."""
    with _lock:
        existing = _tasks.get(source_key)
        if existing and existing.status == TaskStatus.PROCESSING:
            return None
        _prune_finished()
        task = ImageTask(source_key=source_key, token=CancelToken(parent))
        _tasks[source_key] = task
        return task


def finish_task(source_key: str, status: TaskStatus, error: str | None = None) -> None:
    """Record the terminal status of a task."""
    if status == TaskStatus.PROCESSING:
        raise ValueError("finish_task needs a terminal status")
    with _lock:
        task = _tasks.get(source_key)
        if task is not None:
            task.status = status
            task.error = error


def request_abort(source_key: str) -> bool:
    """Ask the worker handling `source_key` to stop at its next checkpoint."""
    with _lock:
        task = _tasks.get(source_key)
        if task is None or task.status != TaskStatus.PROCESSING:
            return False
    task.token.cancel("Aborted by user")
    logger.info("[image_worker] Abort requested for %s", source_key)
    return True


def get_statuses(keys: list[str]) -> dict[str, TaskStatus]:
    """Status per key; unknown keys are reported as DONE (nothing in flight)."""
    with _lock:
        return {k: (_tasks[k].status if k in _tasks else TaskStatus.DONE) for k in keys}


def is_processing(source_key: str) -> bool:
    with _lock:
        task = _tasks.get(source_key)
        return task is not None and task.status == TaskStatus.PROCESSING
