"""Playground: run a preset (stored or ad hoc) on one uploaded or fetched image. Nothing touches S3.

Inputs are untrusted bytes. They are fully decoded with Pillow (with the process-wide
decompression-bomb limit) before any work, and the CPU-heavy pipeline runs in worker
threads behind a semaphore so a burst of requests cannot exhaust memory or block the loop.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import net
from app.core.imaging import ImageFormat, ImageTooLarge, extension_for, extension_of, format_of_extension, probe
from app.core.preset_config import PresetConfig
from app.core.processor import PresetError
from app.core.rendering import AiModels, EngineChoice, ensure_engine_available, render, resolve_engine
from app.services.preset_service import resolve_preset

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SECONDS = 30.0
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
_SLOTS = asyncio.Semaphore(2)  # at most two playground renders at once


class InvalidImage(ValueError):
    """The input is not a decodable image; the message is safe to show."""


class PresetNotApplicable(ValueError):
    """The preset cannot produce an output for this image; the message is safe to show."""


class AIProcessingError(RuntimeError):
    """The external image model failed."""


@dataclass(frozen=True)
class PlaygroundResult:
    content: bytes
    media_type: str
    filename: str
    elapsed_ms: int


async def resolve_config(db: AsyncSession, preset_id: int | None, config: PresetConfig | None) -> PresetConfig:
    """The ad hoc `config`, or the stored preset's. Raises `PresetNotFound`."""
    if config is not None:
        return config
    return (await resolve_preset(db, preset_id)).config


async def fetch_remote(url: str, max_bytes: int) -> tuple[bytes, str]:
    """Download an image from a user-supplied URL (SSRF-safe). Raises net.UnsafeURLError / net.FetchError."""
    result = await net.safe_get(url, max_bytes=max_bytes, timeout=_FETCH_TIMEOUT_SECONDS, require_image=True)
    return result.content, unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or "image"


def output_stem(filename: str) -> str:
    """Filename stem safe to put in a Content-Disposition header."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return _UNSAFE_CHARS.sub("_", stem).strip("._")[:100] or "image"


def _probe(raw: bytes) -> tuple[ImageFormat | None, int, int]:
    try:
        return probe(raw)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("Image dimensions are too large") from exc
    except Exception as exc:  # Pillow raises many unrelated types for malformed input
        raise InvalidImage("File is not a valid JPEG, PNG or WebP image") from exc


async def run(
    raw: bytes, filename: str, config: PresetConfig, engine: EngineChoice, ai_models: AiModels
) -> PlaygroundResult:
    """Render `raw` with `config`. Raises `EngineUnavailable`, `InvalidImage`,
    `PresetNotApplicable` or `AIProcessingError`."""
    ensure_engine_available(engine, config)
    # Decoding is inside the slot too: a full decode can take hundreds of MB, so parallel
    # requests must not all decode before any of them waits for a slot.
    async with _SLOTS:
        return await _run_in_slot(raw, filename, config, engine, ai_models)


async def _run_in_slot(
    raw: bytes, filename: str, config: PresetConfig, engine: EngineChoice, ai_models: AiModels
) -> PlaygroundResult:
    detected, width, height = await asyncio.to_thread(_probe, raw)
    source_format = detected or format_of_extension(extension_of(filename))
    resolved = resolve_engine(engine, config.ai, width, height)

    started = time.perf_counter()
    try:
        rendered = await asyncio.to_thread(
            render, raw, config, source_format=source_format, ai_models=ai_models, choice=resolved
        )
    except (PresetError, ImageTooLarge) as exc:
        raise PresetNotApplicable(str(exc)) from exc
    except Exception as exc:
        if resolved == "local":
            raise
        logger.exception("[playground] %s processing failed", resolved)
        raise AIProcessingError(f"{resolved} processing failed") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    output = rendered.image
    ext = extension_for(output.format, extension_of(filename))
    return PlaygroundResult(output.data, output.content_type, f"{output_stem(filename)}_processed.{ext}", elapsed_ms)
