"""URL import API — routes only. Logic lives in services/import_service.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.schema import ImportRequest, ImportResult
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/", response_model=ImportResult, summary="Import images from URLs into the source prefix")
async def import_images(
    body: ImportRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> ImportResult:
    """Per-URL failures are reported in `failed`; the request itself succeeds."""
    return await import_service.import_urls(db, list(dict.fromkeys(body.urls)), body.folder, actor=actor.username)
