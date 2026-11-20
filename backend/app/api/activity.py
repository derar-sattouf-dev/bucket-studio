"""Activity log API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import get_activity_log, get_batch_history
from app.db.models import ActivityLog, BatchJobHistory
from app.db.session import get_db
from app.models.schema import ActivityLogOut, BatchHistoryOut

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/", response_model=list[ActivityLogOut])
async def list_activity(
    limit: int = Query(50, ge=1, le=200),
    search: str = Query("", max_length=200),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityLog]:
    return await get_activity_log(db, limit, search=search)


@router.get("/batch-history", response_model=list[BatchHistoryOut])
async def list_batch_history(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[BatchJobHistory]:
    return await get_batch_history(db, limit)
