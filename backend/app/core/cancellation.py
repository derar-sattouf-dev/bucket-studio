"""Cooperative cancellation for long-running, thread-pool image work.

Work is never interrupted from the outside. Instead every unit of work carries a
`CancelToken`; the worker calls `token.check()` at safe points (between pipeline
stages, between images, before retries) and unwinds with `Cancelled` when a stop
was requested. Tokens can be chained so that stopping a batch job cancels every
image token created under it.
"""

from __future__ import annotations

import threading


class Cancelled(Exception):
    """Raised at a checkpoint after cancellation was requested."""


class CancelToken:
    """Thread-safe, one-way cancellation flag with an optional parent."""

    __slots__ = ("_event", "_parent", "_reason")

    def __init__(self, parent: CancelToken | None = None) -> None:
        self._event = threading.Event()
        self._parent = parent
        self._reason = "Cancelled"

    def cancel(self, reason: str = "Cancelled") -> None:
        """Request cancellation. Idempotent; the first reason wins."""
        if not self._event.is_set():
            self._reason = reason
            self._event.set()

    @property
    def cancelled(self) -> bool:
        if self._event.is_set():
            return True
        return self._parent is not None and self._parent.cancelled

    @property
    def reason(self) -> str:
        if self._event.is_set() or self._parent is None:
            return self._reason
        return self._parent.reason

    def check(self) -> None:
        """Checkpoint: raise `Cancelled` if this token (or an ancestor) was cancelled."""
        if self.cancelled:
            raise Cancelled(self.reason)
