"""Request authentication and authorisation dependencies.

Two credential types are accepted:

* `Authorization: Bearer <jwt>` — browser sessions. The user is re-loaded on every request,
  so deleting or deactivating a user revokes access immediately.
* `X-API-Key: <key>` — optional static key for server-to-server integrations.
  Treated as an admin principal. Never ship this key to a browser.

Roles: the bootstrap account (`AUTH_USERNAME`) and the API key are admins; DB users are admins
only when `is_admin` is set. Sensitive actions additionally require the `ADMIN_PASSWORD`
step-up secret (see `verify_admin_password`).
"""

import logging
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import rate_limit
from app.core.jwt import verify_token
from app.db.crud import get_user_by_username
from app.db.session import get_db

logger = logging.getLogger(__name__)

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)

API_KEY_PRINCIPAL = "api-key"


@dataclass(frozen=True)
class CurrentUser:
    username: str
    is_admin: bool

    def __str__(self) -> str:  # used in activity-log messages
        return self.username


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def is_bootstrap_admin(username: str) -> bool:
    return bool(settings.auth_username and settings.auth_password) and secrets.compare_digest(
        username.encode(), settings.auth_username.encode()
    )


async def resolve_user(username: str, db: AsyncSession) -> CurrentUser | None:
    """Map a token subject to an active principal, or None if it no longer exists."""
    if is_bootstrap_admin(username):
        return CurrentUser(username=username, is_admin=True)
    user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    return CurrentUser(username=user.username, is_admin=bool(user.is_admin))


async def get_current_user(
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    api_key: str | None = Security(_api_key_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if bearer is not None:
        username = verify_token(bearer.credentials)
        if username:
            principal = await resolve_user(username, db)
            if principal is not None:
                return principal
        raise _unauthorized()

    if api_key and settings.api_key and secrets.compare_digest(api_key.encode(), settings.api_key.encode()):
        return CurrentUser(username=API_KEY_PRINCIPAL, is_admin=True)

    raise _unauthorized()


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


# The step-up password is the last line of defence when an admin session or the API key is stolen,
# so guessing it is throttled per principal.
_STEP_UP_MAX_ATTEMPTS = 5
_STEP_UP_WINDOW_SECONDS = 15 * 60


def verify_admin_password(password: str, actor: CurrentUser) -> None:
    """Step-up check for destructive actions. Raises 503 if unset, 429 if throttled, 403 if wrong."""
    if not settings.admin_password:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_PASSWORD is not configured")
    key = f"step-up:{actor.username}"
    wait = rate_limit.reserve(((key, _STEP_UP_MAX_ATTEMPTS),), _STEP_UP_WINDOW_SECONDS)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many incorrect admin passwords. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    if not secrets.compare_digest(password.encode(), settings.admin_password.encode()):
        logger.warning("Incorrect admin (step-up) password from %s", actor.username)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Incorrect admin password")
    rate_limit.forgive(clear=(key,))
