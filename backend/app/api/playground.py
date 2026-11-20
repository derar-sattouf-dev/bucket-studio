"""Playground API: try a preset on one image (upload or URL). Nothing is stored.

The response body is the processed image, with `Content-Disposition` (attachment file name)
and `X-Processing-Ms` headers.
"""

import logging
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import net
from app.core.preset_config import PresetConfig
from app.core.rendering import AiModels, EngineChoice, EngineUnavailable
from app.db.session import get_db
from app.models.schema import PlaygroundUrlRequest
from app.services import playground_service
from app.services.playground_service import AIProcessingError, InvalidImage, PresetNotApplicable
from app.services.preset_service import PresetConflict, PresetNotFound
from app.services.settings_service import SettingsOut, get_runtime_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playground", tags=["playground"])

_UPLOAD_CHUNK_BYTES = 1024 * 1024
_MAX_CONFIG_JSON_LENGTH = 64 * 1024


async def _read_upload(file: UploadFile, rs: SettingsOut) -> bytes:
    """Read an upload in chunks, enforcing the configured size limit (413)."""
    chunks: list[bytes] = []
    received = 0
    while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
        received += len(chunk)
        if received > rs.max_upload_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File exceeds the {rs.max_upload_mb} MB limit")
        chunks.append(chunk)
    if not received:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    return b"".join(chunks)


def _parse_config(raw: str) -> PresetConfig:
    try:
        return PresetConfig.model_validate_json(raw)
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_input=False)
        raise RequestValidationError([{**e, "loc": ("body", "config", *e["loc"])} for e in errors]) from exc


async def _config(db: AsyncSession, preset_id: int | None, config: PresetConfig | None) -> PresetConfig:
    try:
        return await playground_service.resolve_config(db, preset_id, config)
    except PresetNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preset not found") from exc
    except PresetConflict as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


async def _render(raw: bytes, filename: str, config: PresetConfig, engine: EngineChoice, rs: SettingsOut) -> Response:
    models = AiModels(rs.openai_image_model, rs.gemini_image_model)
    try:
        result = await playground_service.run(raw, filename, config, engine, models)
    except InvalidImage as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except (EngineUnavailable, PresetNotApplicable) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except AIProcessingError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Processing-Ms": str(result.elapsed_ms),
        },
    )


@router.post("/", summary="Process an uploaded image with a preset (or an ad hoc config)")
async def playground_upload(
    file: Annotated[UploadFile, File()],
    preset_id: Annotated[int | None, Form(ge=1)] = None,
    config: Annotated[str | None, Form(max_length=_MAX_CONFIG_JSON_LENGTH)] = None,
    engine: Annotated[EngineChoice, Form()] = "preset",
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Give exactly one of `preset_id` and `config` (a JSON-encoded preset config)."""
    if (preset_id is None) == (config is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give exactly one of preset_id and config")
    parsed = _parse_config(config) if config is not None else None
    resolved = await _config(db, preset_id, parsed)
    rs = await get_runtime_settings(db)
    raw = await _read_upload(file, rs)
    return await _render(raw, file.filename or "image", resolved, engine, rs)


@router.post("/from-url", summary="Fetch an image from a URL and process it with a preset")
async def playground_from_url(body: PlaygroundUrlRequest, db: AsyncSession = Depends(get_db)) -> Response:
    resolved = await _config(db, body.preset_id, body.config)
    rs = await get_runtime_settings(db)
    try:
        raw, filename = await playground_service.fetch_remote(body.url, rs.max_remote_fetch_bytes)
    except net.UnsafeURLError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "URL not allowed") from exc
    except net.FetchError as exc:
        logger.info("[playground] fetch failed for host %s: %s", urlsplit(body.url).hostname, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not fetch image") from exc
    return await _render(raw, filename, resolved, body.engine, rs)
