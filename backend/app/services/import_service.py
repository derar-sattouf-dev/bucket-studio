"""Import images from URLs into the bucket, under the source prefix, as pending images.

Each URL is fetched through the SSRF guard (`net.safe_get`), fully decoded with Pillow, and
stored byte-for-byte with a sanitized, de-duplicated file name whose extension comes from
the detected format (never from the URL). New keys are inserted into the DB directly, so
no re-sync is needed.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import net
from app.core.imaging import CONTENT_TYPES, ImageFormat, probe
from app.core.s3 import CACHE_MUTABLE, get_s3_client, object_exists, put_image
from app.db.crud import get_images_by_keys, log_activity, upsert_images
from app.models.schema import FailedImport, ImportedImage, ImportResult
from app.services.settings_service import SettingsOut, get_runtime_settings

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SECONDS = 30.0
_FETCH_CONCURRENCY = 4
_MAX_STEM_LENGTH = 100
_MAX_NAME_ATTEMPTS = 1000
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_FORMAT_EXTENSIONS: dict[ImageFormat, tuple[str, ...]] = {"jpeg": ("jpg", "jpeg"), "png": ("png",), "webp": ("webp",)}

# Shared by every import request: bounds how many downloaded images are in memory at once.
_fetch_slots = asyncio.Semaphore(_FETCH_CONCURRENCY)

# Name allocation + upload are serialized so two imports never pick the same key
# (the app runs as a single process).
_store_lock = asyncio.Lock()


class ImportFailed(Exception):
    """One URL could not be imported; the message is safe to show."""


@dataclass(frozen=True)
class _Downloaded:
    url: str
    content: bytes
    format: ImageFormat


def _host(url: str) -> str:
    """Host only, for logs: the path and query of a user-supplied URL may carry access tokens."""
    return urlsplit(url).hostname or "?"


def safe_stem(url: str) -> str:
    """File stem from the URL path: decoded, extension dropped, reduced to [A-Za-z0-9._-]."""
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    stem = name.rsplit(".", 1)[0] if "." in name else name
    cleaned = _UNSAFE_CHARS.sub("-", stem).strip("-._")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    return cleaned[:_MAX_STEM_LENGTH].rstrip("-._") or "image"


def _extension_for(fmt: ImageFormat, rs: SettingsOut) -> str:
    for ext in _FORMAT_EXTENSIONS[fmt]:
        if ext in rs.source_filters.extensions:
            return ext
    raise ImportFailed(f"{fmt.upper()} files are not enabled in the source filters")


def _decode(content: bytes) -> ImageFormat:
    try:
        fmt, _, _ = probe(content)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImportFailed("Image is too large") from exc
    except Exception as exc:  # Pillow raises many unrelated types for malformed input
        raise ImportFailed("Not a valid image (use JPEG, PNG or WebP)") from exc
    if fmt is None:
        raise ImportFailed("Unsupported image format (use JPEG, PNG or WebP)")
    return fmt


async def _download(url: str, max_bytes: int) -> _Downloaded:
    try:
        result = await net.safe_get(url, max_bytes=max_bytes, timeout=_FETCH_TIMEOUT_SECONDS, require_image=True)
    except net.UnsafeURLError as exc:
        raise ImportFailed("URL not allowed") from exc
    except net.FetchError as exc:
        logger.info("[import] fetch failed for host %s: %s", _host(url), exc)
        raise ImportFailed("Could not fetch image") from exc
    fmt = await asyncio.to_thread(_decode, result.content)
    return _Downloaded(url, result.content, fmt)


async def _free_key(db: AsyncSession, folder_key: str, stem: str, ext: str, taken: set[str]) -> str:
    """First of `stem.ext`, `stem-2.ext`, … unused in the bucket, the DB and this batch."""
    s3 = get_s3_client()
    for n in range(1, _MAX_NAME_ATTEMPTS + 1):
        key = f"{folder_key}{stem}{'' if n == 1 else f'-{n}'}.{ext}"
        if key in taken or await get_images_by_keys(db, [key]):
            continue
        if not await asyncio.to_thread(object_exists, s3, settings.s3_bucket, key):
            return key
    raise ImportFailed("Could not find a free file name")


async def _store(db: AsyncSession, item: _Downloaded, folder_key: str, rs: SettingsOut, taken: set[str]) -> str:
    ext = _extension_for(item.format, rs)
    key = await _free_key(db, folder_key, safe_stem(item.url), ext, taken)
    if not rs.source_matcher().matches(key):
        raise ImportFailed("The file name is excluded by the source filters")
    await asyncio.to_thread(
        put_image,
        get_s3_client(),
        settings.s3_bucket,
        key,
        item.content,
        CONTENT_TYPES[item.format],
        acl=rs.s3_object_acl,
        cache_control=CACHE_MUTABLE,
    )
    await upsert_images(db, [(key, len(item.content))], rs.source_prefix, rs.group_depth)
    taken.add(key)
    return key


async def import_urls(db: AsyncSession, urls: list[str], folder: str, *, actor: str) -> ImportResult:
    """Fetch, verify and store every URL under `<source_prefix><folder>`. Never raises per URL.

    Each image is stored as soon as it is downloaded, inside the fetch slot, so memory holds at most
    `_FETCH_CONCURRENCY` images at a time however many URLs (or concurrent requests) there are.
    """
    rs = await get_runtime_settings(db)
    folder_key = f"{rs.source_prefix}{folder}"
    taken: set[str] = set()

    async def import_one(url: str) -> ImportedImage | FailedImport:
        async with _fetch_slots:
            try:
                item = await _download(url, rs.max_remote_fetch_bytes)
                async with _store_lock:  # also keeps the shared DB session to one user at a time
                    key = await _store(db, item, folder_key, rs, taken)
            except ImportFailed as exc:
                return FailedImport(url=url, error=str(exc))
            except Exception:
                logger.exception("[import] could not store an image from %s", _host(url))
                return FailedImport(url=url, error="Could not store image")
            return ImportedImage(url=url, key=key, size=len(item.content))

    outcomes = await asyncio.gather(*(import_one(url) for url in urls))
    imported = [o for o in outcomes if isinstance(o, ImportedImage)]
    failed = [o for o in outcomes if isinstance(o, FailedImport)]

    await log_activity(
        db,
        "import.created",
        f"{actor} imported {len(imported)}/{len(urls)} image(s) into {folder_key}",
        {"keys": [i.key for i in imported][:10], "failed": len(failed)},
        username=actor,
    )
    return ImportResult(imported=imported, failed=failed)
