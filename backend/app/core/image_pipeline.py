"""Process one stored image end to end: S3 download → preset render → S3 upload,
with DB status bookkeeping and cooperative cancellation.

`run_pipeline` is synchronous (boto3, Pillow, ONNX, torch) and runs on a dedicated thread pool.
`process_key` is the async wrapper used by both the Images page and batch jobs: it owns the
status transitions `processing → processed | failed` and the in-memory task status.

Cancellation lands at the next checkpoint: before the download, between pipeline stages,
before every retry and right before the upload. The upload is the commit point: once it
has started the image is completed and marked processed, so an aborted image never leaves
a half-written output that is recorded as processed.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import re
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, UnidentifiedImageError

from app.config import MAX_PROCESS_CONCURRENCY, settings
from app.core.ai_prompts import ImageModelError
from app.core.cancellation import Cancelled, CancelToken
from app.core.derivatives import render_all
from app.core.image_worker import ImageTask, TaskStatus, finish_task
from app.core.imaging import ImageTooLarge, extension_for, extension_of, format_of_extension
from app.core.preset_config import ResolvedPreset
from app.core.processor import PresetError
from app.core.rendering import AiModels, EngineChoice, EngineUnavailable, render
from app.core.s3 import CACHE_IMMUTABLE, CACHE_MUTABLE, download_bytes, get_s3_client, put_image
from app.db.crud import MAX_ERROR_MESSAGE_LENGTH, mark_aborted, mark_failed, mark_processed, mark_processing
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from app.services.settings_service import SettingsOut

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_NON_RETRYABLE = (
    Cancelled,
    Image.DecompressionBombError,
    Image.DecompressionBombWarning,
    UnidentifiedImageError,
    PresetError,
    ImageTooLarge,
    EngineUnavailable,
)

# Whole-image jobs get their own threads. On asyncio's default pool (min(32, cpu + 4) threads) a
# raised `process_concurrency` would starve every other `asyncio.to_thread` call (listing, signing,
# publishing) for as long as images are being processed.
_PIPELINE_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_PROCESS_CONCURRENCY, thread_name_prefix="pipeline")


class Outcome(StrEnum):
    PROCESSED = "processed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass(frozen=True)
class ProcessingPlan:
    """Everything needed to process an image, resolved once per request or job."""

    runtime: SettingsOut
    preset: ResolvedPreset
    engine: EngineChoice = "preset"
    prompt: str | None = None
    overwrite_source: bool = False
    output_prefix: str | None = None  # defaults to runtime.output_prefix
    max_attempts: int = 1


@dataclass(frozen=True)
class PipelineResult:
    output_key: str
    output_size: int
    processed_by: str
    source_width: int
    source_height: int


def describe_error(exc: BaseException) -> str:
    """Error text **for the server log only**: URLs (possibly signed) removed, whitespace collapsed, capped."""
    text = _URL_RE.sub("<url>", str(exc)) or type(exc).__name__
    return " ".join(text.split())[:MAX_ERROR_MESSAGE_LENGTH]


# Raised by this app with a message written for the person using it.
_OWN_MESSAGES = (PresetError, ImageTooLarge, EngineUnavailable, ImageModelError)
_STORAGE_CODE = re.compile(r"[A-Za-z0-9]{1,40}")


def public_error(exc: BaseException) -> str:
    """The message stored on the image and returned by the API.

    Never the raw exception text: library errors (storage, Pillow, torch, the AI providers) can
    name buckets, hosts and internals. Unknown failures get a generic line; the detail is in the log.
    """
    if isinstance(exc, _OWN_MESSAGES):
        return str(exc)[:MAX_ERROR_MESSAGE_LENGTH]
    if isinstance(exc, Image.DecompressionBombError | Image.DecompressionBombWarning):
        return "The image dimensions are too large"
    if isinstance(exc, UnidentifiedImageError):
        return "The file is not a valid JPEG, PNG or WebP image"
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
        return f"Storage error ({code})" if _STORAGE_CODE.fullmatch(code) else "Storage error"
    if isinstance(exc, BotoCoreError):
        return "Could not reach the storage service"
    if isinstance(exc, MemoryError):
        return "Not enough memory to process this image"
    return "Processing failed (details are in the server log)"


def output_key_for(source_key: str, output_ext: str, plan: ProcessingPlan) -> str:
    """Where the processed image is written: the source key itself, or `<output_prefix><key>`
    with the extension of the output format."""
    if plan.overwrite_source:
        return source_key
    prefix = plan.output_prefix if plan.output_prefix is not None else plan.runtime.output_prefix
    return f"{prefix}{source_key.rsplit('.', 1)[0]}.{output_ext}"


def run_pipeline(key: str, plan: ProcessingPlan, token: CancelToken) -> PipelineResult:
    """Synchronously produce and upload the processed image for `key`."""
    s3, bucket = get_s3_client(), settings.s3_bucket

    token.check()
    raw = download_bytes(s3, bucket, key)

    token.check()
    source_ext = extension_of(key)
    source_format = format_of_extension(source_ext)
    rendered = render(
        raw,
        plan.preset.config,
        source_format=source_format,
        ai_models=AiModels(plan.runtime.openai_image_model, plan.runtime.gemini_image_model),
        choice=plan.engine,
        prompt=plan.prompt,
        checkpoint=token.check,
    )
    output = rendered.image

    derivatives = []
    if plan.overwrite_source:
        if output.format != source_format:
            raise PresetError("Overwriting the original needs a preset that keeps the source format")
        # The source itself changes, so its derivatives must follow.
        derivatives = render_all(output.data, plan.runtime.publish, key, output.format)

    # Last checkpoint: from here on the upload is committed and the image is completed.
    token.check()
    out_key = output_key_for(key, extension_for(output.format, source_ext), plan)
    cache = CACHE_MUTABLE if plan.overwrite_source else CACHE_IMMUTABLE
    acl = plan.runtime.s3_object_acl
    put_image(s3, bucket, out_key, output.data, output.content_type, acl=acl, cache_control=cache)
    for derivative in derivatives:
        put_image(s3, bucket, derivative.key, derivative.data, derivative.content_type, acl=acl)

    return PipelineResult(
        out_key, len(output.data), rendered.processed_by, rendered.source_width, rendered.source_height
    )


async def _wait_or_cancel(token: CancelToken, seconds: float) -> None:
    """Async sleep that raises `Cancelled` as soon as the token is cancelled."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while (remaining := deadline - loop.time()) > 0:
        token.check()
        await asyncio.sleep(min(0.25, remaining))
    token.check()


async def _run_with_retries(key: str, plan: ProcessingPlan, token: CancelToken) -> PipelineResult:
    attempt = 1
    loop = asyncio.get_running_loop()
    while True:
        try:
            # Like `asyncio.to_thread` (context variables included), but on the pipeline's own pool.
            context = contextvars.copy_context()
            return await loop.run_in_executor(_PIPELINE_EXECUTOR, context.run, run_pipeline, key, plan, token)
        except _NON_RETRYABLE:
            raise
        except Exception as exc:
            if attempt >= plan.max_attempts:
                raise
            delay = 2 ** (attempt - 1)
            logger.warning(
                "Transient error on %s (attempt %d/%d), retrying in %ds: %s",
                key,
                attempt,
                plan.max_attempts,
                delay,
                describe_error(exc),
            )
            await _wait_or_cancel(token, delay)
            attempt += 1


async def process_key(task: ImageTask, plan: ProcessingPlan) -> Outcome:
    """Process a registered image task and record the result in the DB and task registry.

    Never raises for per-image problems; the outcome says what happened.
    """
    key, token = task.source_key, task.token
    status: TaskStatus = TaskStatus.FAILED
    error: str | None = "Interrupted"
    started = False
    try:
        token.check()
        async with AsyncSessionLocal() as db:
            await mark_processing(db, key, plan.preset.id)
        started = True

        result = await _run_with_retries(key, plan, token)

        async with AsyncSessionLocal() as db:
            await mark_processed(
                db,
                key,
                result.output_key,
                result.output_size,
                processed_by=result.processed_by,
                source_width=result.source_width,
                source_height=result.source_height,
            )
        status, error = TaskStatus.DONE, None
        return Outcome.PROCESSED

    except Cancelled as exc:
        status, error = TaskStatus.ABORTED, str(exc)
        logger.info("Processing of %s stopped: %s", key, exc)
        if started:
            await _record_safely(key, mark_aborted)
        return Outcome.ABORTED

    except Exception as exc:
        error = public_error(exc)
        logger.error("Processing failed for %s: %s", key, describe_error(exc), exc_info=True)
        await _record_safely(key, mark_failed, error)
        return Outcome.FAILED

    finally:
        finish_task(key, status, error)


async def _record_safely(key: str, mark: Callable[..., Awaitable[None]], *args: str) -> None:
    """Best-effort status write used on error paths (a DB failure must not mask the outcome)."""
    try:
        async with AsyncSessionLocal() as db:
            await mark(db, key, *args)
    except Exception:
        logger.exception("Could not record final status for %s", key)
