"""Small pieces shared by more than one router."""

from fastapi import HTTPException, status

from app.core.auth import CurrentUser

# Server-Sent Events must reach the client as they are produced: no caching, no proxy buffering.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def require_admin_for_overwrite(overwrite: bool, actor: CurrentUser) -> None:
    """Overwriting originals in place keeps no backup, so it is restricted to admins."""
    if overwrite and not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can overwrite original images")
