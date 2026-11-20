"""S3-compatible storage helpers (MinIO, AWS S3, DigitalOcean Spaces, R2, …).

All functions are synchronous boto3 calls: from async code, run them with
`asyncio.to_thread`. The boto3 clients are thread-safe and shared.

Two clients exist: one for real operations (`S3_ENDPOINT_URL`) and one used only to sign
browser-facing URLs (`S3_PUBLIC_ENDPOINT_URL`, when the browser reaches the storage under
another host name than the backend does). Signing is local and needs no network access.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.core.source_filters import SourceMatcher

logger = logging.getLogger(__name__)

CACHE_MUTABLE = "public, max-age=3600, must-revalidate"
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
_NOT_FOUND_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


def _make_client(endpoint_url: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        # None (not "") lets botocore fall back to its credential chain: instance roles, IRSA, ...
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.s3_addressing_style},
            request_checksum_calculation=settings.s3_checksum_mode,
            response_checksum_validation=settings.s3_checksum_mode,
            retries={"max_attempts": 5, "mode": "standard"},
            connect_timeout=10,
            read_timeout=60,
            max_pool_connections=32,
        ),
    )


@lru_cache(maxsize=1)
def get_s3_client() -> Any:
    """The shared client for real storage operations."""
    return _make_client(settings.s3_endpoint_url)


@lru_cache(maxsize=1)
def get_presign_client() -> Any:
    """The client used to sign browser-facing GET URLs."""
    if settings.s3_public_endpoint_url:
        return _make_client(settings.s3_public_endpoint_url)
    return get_s3_client()


# ── Listing / transfer ────────────────────────────────────────────────────────


def iter_source_keys(
    s3_client: Any,
    bucket: str,
    prefix: str,
    matcher: SourceMatcher,
    exclude_prefixes: Iterable[str] = (),
    chunk_size: int = 200,
) -> Iterator[list[tuple[str, int]]]:
    """Yield chunks of `(key, size)` for source images under `prefix`.

    Paginates, so it handles 100k+ keys without loading the listing into memory. Keys
    under any of `exclude_prefixes` (processed output, backups) are skipped.
    """
    excluded = tuple(p for p in exclude_prefixes if p)
    paginator = s3_client.get_paginator("list_objects_v2")
    chunk: list[tuple[str, int]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if (excluded and key.startswith(excluded)) or not matcher.matches(key):
                continue
            chunk.append((key, obj.get("Size", 0)))
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
    if chunk:
        yield chunk


def download_bytes(s3_client: Any, bucket: str, key: str) -> bytes:
    """Download an object into memory (never to disk)."""
    return s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()


def put_image(
    s3_client: Any,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
    *,
    acl: str,
    cache_control: str = CACHE_MUTABLE,
) -> None:
    """Upload an image with the canned `acl` ('' = none). Use `CACHE_IMMUTABLE` only for keys that never change."""
    extra = {"ACL": acl} if acl else {}
    s3_client.put_object(
        Bucket=bucket, Key=key, Body=data, ContentType=content_type, CacheControl=cache_control, **extra
    )
    logger.debug("Uploaded %s to s3://%s/%s", content_type, bucket, key)


def copy_object(s3_client: Any, bucket: str, src_key: str, dest_key: str, *, acl: str = "") -> None:
    """Server-side copy (metadata kept). Without `acl` the bucket default applies (used for backups)."""
    extra = {"ACL": acl} if acl else {}
    s3_client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": src_key}, Key=dest_key, **extra)


def delete_object(s3_client: Any, bucket: str, key: str) -> None:
    s3_client.delete_object(Bucket=bucket, Key=key)


def object_exists(s3_client: Any, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
            return False
        raise
    return True


# ── Presigned URLs ────────────────────────────────────────────────────────────

# (key, expires_in) → (url, refresh_at): a changed expiry never reuses URLs signed for the old one.
# Least recently used first: a full cache drops its oldest entries, never everything at once.
_presign_cache: OrderedDict[tuple[str, int], tuple[str, float]] = OrderedDict()
_presign_lock = threading.Lock()
_PRESIGN_CACHE_MAX = 5000


def _presign_cache_ttl(expires_in: int) -> float:
    """Reuse a URL until a few minutes before it expires."""
    return max(expires_in - 300, expires_in / 2)


def presign_get(key: str | None, expires_in: int) -> str | None:
    """Cached presigned GET URL for `key` (None if there is no key or signing fails)."""
    if not key:
        return None
    cache_key = (key, expires_in)
    now = time.monotonic()
    with _presign_lock:
        cached = _presign_cache.get(cache_key)
        if cached and cached[1] > now:
            _presign_cache.move_to_end(cache_key)
            return cached[0]
    try:
        url = get_presign_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as exc:
        logger.warning("Presign failed for %s: %s", key, type(exc).__name__)
        return None
    with _presign_lock:
        _presign_cache[cache_key] = (url, now + _presign_cache_ttl(expires_in))
        _presign_cache.move_to_end(cache_key)
        while len(_presign_cache) > _PRESIGN_CACHE_MAX:
            _presign_cache.popitem(last=False)
    return url
