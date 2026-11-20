"""Sign-in use case: throttling, credential check, audit log and token issue."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import rate_limit
from app.core.auth import is_bootstrap_admin
from app.core.jwt import create_token
from app.core.passwords import verify_password_async
from app.db.crud import get_user_by_username, log_activity
from app.services.settings_service import get_runtime_settings


class InvalidCredentials(Exception):
    """Unknown user, wrong password or deactivated account (deliberately indistinguishable)."""


class LoginThrottled(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Session:
    token: str
    expires_in: int  # seconds


async def _authenticate(db: AsyncSession, username: str, password: str) -> bool:
    # The bootstrap name is checked first, exactly as `resolve_user` does: if AUTH_USERNAME is ever
    # set to an existing user's name, that user's own password must not open the admin account.
    if is_bootstrap_admin(username):
        await verify_password_async(password, None)  # same bcrypt cost as a DB user, for timing parity
        return secrets.compare_digest(password.encode(), settings.auth_password.encode())
    user = await get_user_by_username(db, username)
    if user is not None:
        return await verify_password_async(password, user.password_hash) and user.is_active
    await verify_password_async(password, None)  # equalise timing for unknown users
    return False


async def login(db: AsyncSession, username: str, password: str, *, ip: str) -> Session:
    """Check the credentials and issue a token. Raises `LoginThrottled` or `InvalidCredentials`."""
    rs = await get_runtime_settings(db)
    limits = rate_limit.LoginLimits(rs.login_max_attempts, rs.login_lockout_minutes)
    # The attempt is counted before the password is checked (and forgiven on success), so parallel
    # guesses cannot all slip under the limit.
    wait = rate_limit.reserve_login(ip, username, limits)
    if wait:
        raise LoginThrottled(wait)

    if not await _authenticate(db, username, password):
        await log_activity(
            db, "auth.login_failed", f"Failed login attempt for '{username}'", {"ip": ip}, username=username
        )
        raise InvalidCredentials

    rate_limit.forgive_login(ip, username)
    await log_activity(db, "auth.login", f"User '{username}' logged in", {"ip": ip}, username=username)
    return Session(token=create_token(username, rs.session_minutes), expires_in=rs.session_minutes * 60)
