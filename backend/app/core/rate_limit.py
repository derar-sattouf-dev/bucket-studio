"""In-memory attempt throttling (logins and the admin step-up password).

The app runs as a single process (see docs/architecture.md), so an in-process store is sufficient.

An attempt is *reserved* before the secret is checked and *forgiven* if the check succeeds. Counting
first closes the check-then-act gap: a burst of parallel guesses cannot all pass the limit before
any of them has been recorded as a failure.

Logins are tracked per (client IP, username) and per client IP; either one exceeding its budget
locks further attempts until the window expires. The limits are runtime settings, passed in at
check time so changes apply immediately.
"""

import threading
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LoginLimits:
    max_attempts: int
    lockout_minutes: int


_lock = threading.Lock()
_attempts: dict[str, deque[float]] = {}

# A single IP may try several usernames; allow it a larger budget than one username.
_IP_MULTIPLIER = 4
# Idle keys are swept once the table grows past this, so it cannot grow without bound.
_SWEEP_ABOVE = 10_000
# No window is longer than this (the lockout setting is capped well below it).
_MAX_WINDOW_SECONDS = 24 * 3600.0


def _prune(bucket: deque[float], now: float, window: float) -> None:
    while bucket and bucket[0] <= now - window:
        bucket.popleft()


def _sweep(now: float) -> None:
    for key in [k for k, bucket in _attempts.items() if not bucket or bucket[-1] <= now - _MAX_WINDOW_SECONDS]:
        del _attempts[key]


def reserve(budgets: Sequence[tuple[str, int]], window_seconds: float) -> int:
    """Count one attempt against every `(key, limit)` budget, atomically.

    Returns 0 if the attempt may proceed, otherwise the seconds until one is allowed again (in
    which case nothing is counted).
    """
    now = time.monotonic()
    with _lock:
        if len(_attempts) > _SWEEP_ABOVE:
            _sweep(now)
        wait = 0.0
        for key, limit in budgets:
            bucket = _attempts.get(key)
            if not bucket:
                continue
            _prune(bucket, now, window_seconds)
            if len(bucket) >= limit:
                wait = max(wait, bucket[0] + window_seconds - now)
        if wait > 0:
            return int(wait) + 1
        for key, _ in budgets:
            _attempts.setdefault(key, deque()).append(now)
    return 0


def forgive(clear: Sequence[str] = (), refund: Sequence[str] = ()) -> None:
    """After a successful check: forget the `clear` keys and take the reserved attempt back from `refund`."""
    with _lock:
        for key in clear:
            _attempts.pop(key, None)
        for key in refund:
            bucket = _attempts.get(key)
            if bucket:
                bucket.pop()
                if not bucket:
                    del _attempts[key]


def _login_keys(ip: str, username: str) -> tuple[str, str]:
    return f"login:{ip}:{username.lower()}", f"login-ip:{ip}"


def reserve_login(ip: str, username: str, limits: LoginLimits) -> int:
    """Count a login attempt. Returns seconds to wait (0 = go ahead and check the password)."""
    user_key, ip_key = _login_keys(ip, username)
    budgets = ((user_key, limits.max_attempts), (ip_key, limits.max_attempts * _IP_MULTIPLIER))
    return reserve(budgets, limits.lockout_minutes * 60)


def forgive_login(ip: str, username: str) -> None:
    user_key, ip_key = _login_keys(ip, username)
    forgive(clear=(user_key,), refund=(ip_key,))


def clear_all() -> None:
    """Testing helper."""
    with _lock:
        _attempts.clear()
