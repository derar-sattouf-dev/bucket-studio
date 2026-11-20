"""Stats API — dashboard numbers."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.job_registry import get_running_job
from app.db.crud import get_image_stats
from app.db.session import get_db
from app.models.schema import StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)) -> StatsOut:
    counts = await get_image_stats(db)
    return StatsOut(**counts, job_running=get_running_job() is not None)
