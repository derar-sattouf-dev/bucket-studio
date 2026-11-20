"""Settings API — routes only. Logic lives in services/settings_service.py
and services/settings_admin_service.py.

Reading settings is open to every signed-in user; changing them requires the admin role,
and bucket layout / publishing changes and DB reset additionally require the admin password.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_admin, verify_admin_password
from app.db.session import get_db
from app.services import settings_admin_service
from app.services.preset_service import PresetNotFound
from app.services.settings_service import (
    AdminResetDbRequest,
    AdminSettingsPatch,
    AdminVerifyRequest,
    EnvironmentOut,
    InvalidSettings,
    SettingsOut,
    SettingsPatch,
    environment_info,
    get_runtime_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=SettingsOut)
async def read_settings(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    return await get_runtime_settings(db)


@router.get("/environment", response_model=EnvironmentOut)
async def read_environment() -> EnvironmentOut:
    """Read-only deployment facts (env-only configuration). Contains no secrets."""
    return environment_info()


@router.patch("/", response_model=SettingsOut)
async def patch_settings(
    body: SettingsPatch,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> SettingsOut:
    try:
        return await settings_admin_service.change_runtime_settings(db, body, actor=actor.username)
    except PresetNotFound as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Preset not found") from exc


@router.post("/verify-admin")
async def verify_admin(body: AdminVerifyRequest, actor: CurrentUser = Depends(require_admin)) -> dict[str, bool]:
    verify_admin_password(body.admin_password, actor)
    return {"ok": True}


@router.patch("/admin", response_model=SettingsOut)
async def patch_admin_settings(
    body: AdminSettingsPatch,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> SettingsOut:
    verify_admin_password(body.admin_password, actor)
    try:
        return await settings_admin_service.change_admin_settings(db, body, actor=actor.username)
    except settings_admin_service.NoChanges as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update") from exc
    except InvalidSettings as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/reset-db")
async def reset_db(body: AdminResetDbRequest, actor: CurrentUser = Depends(require_admin)) -> dict[str, object]:
    verify_admin_password(body.admin_password, actor)
    try:
        await settings_admin_service.reset_database(actor=actor.username)
    except settings_admin_service.ResetRefused as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"ok": True, "message": "Database reset successfully"}
