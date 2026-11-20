"""User management use cases behind the Users API (the step-up password is checked by the router)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import API_KEY_PRINCIPAL, is_bootstrap_admin
from app.core.passwords import hash_password_async, validate_password_strength
from app.db import crud
from app.db.models import User


class UserRequestError(Exception):
    """A request that cannot be fulfilled; the message is safe to show."""


class ReservedUsername(UserRequestError):
    pass


class WeakPassword(UserRequestError):
    pass


class OwnAccount(UserRequestError):
    """Admins cannot delete or deactivate the account they are signed in with."""


class UserExists(Exception):
    """The username is taken (by a user or by the bootstrap admin); the message is safe to show."""


class UserNotFound(Exception):
    pass


async def list_users(db: AsyncSession) -> list[User]:
    return await crud.get_all_users(db)


async def create_user(db: AsyncSession, *, username: str, password: str, is_admin: bool, actor: str) -> User:
    if username.lower() == API_KEY_PRINCIPAL:
        # Would be indistinguishable from the API key in the activity log.
        raise ReservedUsername(f"'{API_KEY_PRINCIPAL}' is a reserved name")
    if is_bootstrap_admin(username) or await crud.get_user_by_username(db, username):
        raise UserExists(f"User '{username}' already exists")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise WeakPassword(str(exc)) from exc

    user = await crud.create_user(db, username, await hash_password_async(password), is_admin=is_admin)
    await crud.log_activity(db, "user.created", f"User '{username}' created", {"is_admin": is_admin}, username=actor)
    return user


async def _require(db: AsyncSession, user_id: int) -> User:
    user = await crud.get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFound(user_id)
    return user


async def set_active(db: AsyncSession, user_id: int, is_active: bool, *, actor: str) -> User:
    """Activate or deactivate a user. Deactivation takes effect on the user's next request."""
    user = await _require(db, user_id)
    if not is_active and user.username == actor:
        raise OwnAccount("You cannot deactivate your own account")
    if user.is_active == is_active:
        return user
    user = await crud.set_user_active(db, user, is_active)
    state = "activated" if is_active else "deactivated"
    await crud.log_activity(db, f"user.{state}", f"User '{user.username}' {state}", username=actor)
    return user


async def delete_user(db: AsyncSession, user_id: int, *, actor: str) -> None:
    user = await _require(db, user_id)
    if user.username == actor:
        raise OwnAccount("You cannot delete your own account")
    username = user.username
    await crud.delete_user(db, user_id)
    await crud.log_activity(db, "user.deleted", f"User '{username}' deleted", username=actor)
