"""Images API — routes and HTTP mapping only. Logic lives in services/image_service.py."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import SSE_HEADERS, require_admin_for_overwrite
from app.core.auth import CurrentUser, get_current_user
from app.core.image_worker import TaskStatus, get_statuses
from app.core.rendering import EngineUnavailable
from app.db.crud import GroupScope, ImageListStatus, ImageSortField
from app.db.session import get_db
from app.models.schema import (
    AbortRequest,
    BulkPublishStatus,
    GroupImagesPage,
    GroupSelector,
    KeysRequest,
    PaginatedGroups,
    PaginatedImages,
    ProcessGroupRequest,
    ProcessRequest,
    RetryFailedResult,
    SourceKey,
    UpdateNotesRequest,
)
from app.services import image_service, publish_service
from app.services.image_service import ImageBusy, ImageRequestError, ImagesNotFound, InvalidImageKeys
from app.services.preset_service import PresetConflict, PresetNotFound
from app.services.sync_service import SyncUnavailable, cancel_sync, is_sync_running, sync_bucket

router = APIRouter(prefix="/images", tags=["images"])

_MAX_STREAM_KEYS = 200
_MAX_PAGE = 100_000
_MAX_SEARCH_LENGTH = 200

T = TypeVar("T")


async def _mapped(call: Awaitable[T]) -> T:
    """Await a service call, translating its client errors into HTTP responses."""
    try:
        return await call
    except InvalidImageKeys as exc:
        raise HTTPException(400, str(exc)) from exc
    except ImagesNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ImageBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    except ImageRequestError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PresetNotFound as exc:
        raise HTTPException(404, "Preset not found") from exc
    except (PresetConflict, EngineUnavailable) as exc:
        raise HTTPException(422, str(exc)) from exc


# ── S3 sync ───────────────────────────────────────────────────────────────────


@router.get("/sync-status")
async def sync_status_endpoint() -> dict[str, bool]:
    return {"syncing": is_sync_running()}


@router.post("/sync/cancel")
async def cancel_sync_endpoint(actor: CurrentUser = Depends(get_current_user)) -> dict[str, bool]:
    if not await cancel_sync(actor.username):
        raise HTTPException(409, "No sync is currently running")
    return {"ok": True}


@router.post("/sync", summary="Sync S3 bucket into local DB")
async def sync_images(actor: CurrentUser = Depends(get_current_user)) -> dict[str, int | bool]:
    try:
        result = await sync_bucket("manual", actor=actor.username)
    except SyncUnavailable as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"synced": result.new_images, "auto_processing": result.auto_job_id is not None}


# ── List ──────────────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedGroups)
async def list_images_endpoint(
    response: Response,
    page: int = Query(1, ge=1, le=_MAX_PAGE),
    page_size: int = Query(10, ge=1, le=100),
    status: ImageListStatus | None = Query(None),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LENGTH),
    sort_by: ImageSortField = Query("updated_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedGroups:
    response.headers["Cache-Control"] = "no-cache"
    return await image_service.list_image_groups(
        db,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/group", response_model=GroupImagesPage, summary="More images of one group of the list")
async def group_images_endpoint(
    response: Response,
    group: str | None = Query(None, min_length=1, max_length=1024, description="Omit for the ungrouped images"),
    offset: int = Query(0, ge=0, le=10_000_000),
    limit: int = Query(image_service.GROUP_IMAGE_LIMIT, ge=1, le=100),
    status: ImageListStatus | None = Query(None),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LENGTH),
    sort_by: ImageSortField = Query("updated_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    db: AsyncSession = Depends(get_db),
) -> GroupImagesPage:
    response.headers["Cache-Control"] = "no-cache"
    return await image_service.list_group_page(
        db, GroupScope(group, status, search), offset=offset, limit=limit, sort_by=sort_by, sort_order=sort_order
    )


@router.get("/review", response_model=PaginatedImages, summary="Processed images that are not published yet")
async def review(
    page: int = Query(1, ge=1, le=_MAX_PAGE),
    page_size: int = Query(30, ge=1, le=100),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> PaginatedImages:
    return await image_service.list_review(db, page=page, page_size=page_size, search=search)


@router.get("/failed", response_model=PaginatedImages)
async def failed(
    page: int = Query(1, ge=1, le=_MAX_PAGE),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> PaginatedImages:
    return await image_service.list_failed(db, page=page, page_size=page_size, search=search)


# ── Process ───────────────────────────────────────────────────────────────────


@router.post("/process", summary="Process images with a preset")
async def process_images_endpoint(
    body: ProcessRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    require_admin_for_overwrite(body.replace, actor)
    result = await _mapped(
        image_service.queue_processing(
            db,
            body.keys,
            actor=actor.username,
            preset_id=body.preset_id,
            engine=body.engine,
            prompt=body.prompt,
            replace=body.replace,
        )
    )
    return {
        "queued": result.queued,
        "already_processing": result.already_processing,
        "preset_id": result.preset_id,
        "engine": body.engine,
        "replace": body.replace,
    }


@router.post("/process-group", summary="Process every image of one group with a preset")
async def process_group_endpoint(
    body: ProcessGroupRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    """Like `/process`, but the server collects the group's keys, so the group can be of any size."""
    require_admin_for_overwrite(body.replace, actor)
    result = await _mapped(
        image_service.queue_group_processing(
            db,
            GroupScope(body.group, body.status, body.search),
            actor=actor.username,
            preset_id=body.preset_id,
            engine=body.engine,
            prompt=body.prompt,
            replace=body.replace,
        )
    )
    return {
        "queued": result.queued,
        "skipped_busy": len(result.already_processing),
        "preset_id": result.preset_id,
        "engine": body.engine,
        "replace": body.replace,
    }


@router.post("/abort", summary="Abort a currently processing image")
async def abort_image_endpoint(
    body: AbortRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Request an abort. It takes effect at the image's next pipeline checkpoint; follow
    `/images/stream` to see the status change to `aborted`."""
    await _mapped(image_service.abort_processing(db, body.key, actor=actor.username))
    return {"aborted": body.key}


@router.post("/retry-failed", response_model=RetryFailedResult, summary="Requeue all failed images")
async def retry_failed(
    replace: bool = False,
    max_retries: int | None = Query(None, ge=0, le=10_000, description="Defaults to the max_retry_count setting"),
    preset_id: int | None = Query(None, ge=1, description="Defaults to the default preset"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> RetryFailedResult:
    require_admin_for_overwrite(replace, actor)
    return await _mapped(
        image_service.retry_failed(
            db, actor=actor.username, replace=replace, max_retries=max_retries, preset_id=preset_id
        )
    )


# ── SSE stream ───────────────────────────────────────────────────────────────


@router.get("/stream")
async def stream_image_status(
    keys: Annotated[list[SourceKey], Query(min_length=1, max_length=_MAX_STREAM_KEYS)],
) -> StreamingResponse:
    """Server-Sent Events stream of per-image processing status.

    Closes once every requested key has finished. Each event payload:
      { "statuses": { "<key>": "processing"|"done"|"failed"|"aborted" }, "all_done": bool }
    """
    unique_keys = list(dict.fromkeys(keys))

    async def event_generator() -> AsyncIterator[str]:
        while True:
            statuses = get_statuses(unique_keys)
            all_done = all(s != TaskStatus.PROCESSING for s in statuses.values())
            payload = {"statuses": {k: s.value for k, s in statuses.items()}, "all_done": all_done}
            yield f"data: {json.dumps(payload)}\n\n"
            if all_done:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)


# ── Notes / Tags ──────────────────────────────────────────────────────────────


@router.patch("/notes", summary="Update notes and tags on an image")
async def update_notes_endpoint(
    body: UpdateNotesRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str | None]:
    record = await _mapped(image_service.update_notes(db, body.source_key, body.notes, body.tags, actor=actor.username))
    return {"source_key": record.source_key, "notes": record.notes, "tags": record.tags}


# ── Publish / Restore ─────────────────────────────────────────────────────────


@router.post("/publish", summary="Publish processed images over their sources (with backup) and write derivatives")
async def publish_images_endpoint(
    body: KeysRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    return {"results": await _mapped(publish_service.publish_images(db, body.keys, actor=actor.username))}


async def _start_bulk_publish(db: AsyncSession, actor: CurrentUser, scope: GroupScope | None) -> dict[str, int]:
    try:
        return {"total": await publish_service.start_bulk_publish(db, actor=actor.username, scope=scope)}
    except publish_service.BulkPublishRunning as exc:
        raise HTTPException(409, "A bulk publish is already running") from exc


@router.post("/publish-all", status_code=202, summary="Start publishing every processed, unpublished image")
async def publish_all_endpoint(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    """Runs in the background (one bulk publish at a time); follow `/images/publish-all/status`."""
    return await _start_bulk_publish(db, actor, None)


@router.post("/publish-group", status_code=202, summary="Start publishing the publishable images of one group")
async def publish_group_endpoint(
    body: GroupSelector,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    """Same background run and status as `/publish-all`, limited to one group."""
    return await _start_bulk_publish(db, actor, GroupScope(body.group, body.status, body.search))


@router.get("/publish-all/status", response_model=BulkPublishStatus)
async def publish_all_status_endpoint() -> BulkPublishStatus:
    return BulkPublishStatus.model_validate(publish_service.bulk_publish_status(), from_attributes=True)


@router.post("/restore", summary="Restore originals from the backup (or discard unpublished output)")
async def restore_images_endpoint(
    body: KeysRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    return {"results": await _mapped(publish_service.restore_images(db, body.keys, actor=actor.username))}


@router.post("/reset-pending", summary="Reset images back to pending (DB only, no bucket change)")
async def reset_pending_endpoint(
    body: KeysRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    return {"reset": await _mapped(image_service.reset_to_pending(db, body.keys, actor=actor.username))}
