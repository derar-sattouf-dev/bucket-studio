"""Presets API — routes only. Logic lives in services/preset_service.py.

Every signed-in user can list presets; creating, changing and deleting them requires the admin role.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_admin
from app.db.crud import list_presets
from app.db.models import Preset
from app.db.session import get_db
from app.models.schema import PresetCreate, PresetOut, PresetUpdate
from app.services import preset_service
from app.services.preset_service import PresetConflict, PresetNotFound

router = APIRouter(prefix="/presets", tags=["presets"])

PresetId = Annotated[int, Path(ge=1)]


def _out(preset: Preset) -> PresetOut:
    return PresetOut(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        config=preset_service.config_of(preset),
        is_default=preset.is_default,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PresetNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Preset not found")
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/", response_model=list[PresetOut])
async def get_presets(db: AsyncSession = Depends(get_db)) -> list[PresetOut]:
    return [_out(p) for p in await list_presets(db)]


@router.post("/", response_model=PresetOut, status_code=status.HTTP_201_CREATED)
async def create_preset(
    body: PresetCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> PresetOut:
    try:
        preset = await preset_service.create_preset(
            db, name=body.name, description=body.description, config=body.config, actor=actor.username
        )
    except PresetConflict as exc:
        raise _http_error(exc) from exc
    return _out(preset)


@router.patch("/{preset_id}", response_model=PresetOut)
async def update_preset(
    preset_id: PresetId,
    body: PresetUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> PresetOut:
    try:
        preset = await preset_service.update_preset(
            db, preset_id, name=body.name, description=body.description, config=body.config, actor=actor.username
        )
    except (PresetNotFound, PresetConflict) as exc:
        raise _http_error(exc) from exc
    return _out(preset)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: PresetId,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> Response:
    try:
        await preset_service.delete_preset(db, preset_id, actor=actor.username)
    except (PresetNotFound, PresetConflict) as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{preset_id}/default", response_model=PresetOut)
async def set_default_preset(
    preset_id: PresetId,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_admin),
) -> PresetOut:
    try:
        preset = await preset_service.set_default(db, preset_id, actor=actor.username)
    except PresetNotFound as exc:
        raise _http_error(exc) from exc
    return _out(preset)
