"""User management API (admin role + admin password required for changes).

Routes only. Logic lives in services/user_service.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_admin, verify_admin_password
from app.db.models import User
from app.db.session import get_db
from app.models.schema import CreateUserRequest, DeleteUserRequest, UpdateUserRequest, UserOut
from app.services import user_service
from app.services.user_service import UserExists, UserNotFound, UserRequestError

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])

UserId = Annotated[int, Path(ge=1)]


@router.get("/", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    return await user_service.list_users(db)


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def add_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> User:
    verify_admin_password(body.admin_password, actor)
    try:
        return await user_service.create_user(
            db, username=body.username, password=body.password, is_admin=body.is_admin, actor=actor.username
        )
    except UserExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except UserRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.patch("/{user_id}", response_model=UserOut, summary="Activate or deactivate a user")
async def update_user(
    user_id: UserId,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> User:
    verify_admin_password(body.admin_password, actor)
    try:
        return await user_service.set_active(db, user_id, body.is_active, actor=actor.username)
    except UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    except UserRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UserId,
    body: DeleteUserRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> None:
    verify_admin_password(body.admin_password, actor)
    try:
        await user_service.delete_user(db, user_id, actor=actor.username)
    except UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    except UserRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
