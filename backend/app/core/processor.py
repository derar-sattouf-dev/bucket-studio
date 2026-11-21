"""The local image pipeline: pure functions on Pillow images, driven by a `PresetConfig`.

Stages of `process_image` (each one can be switched off in the preset):
    1. Contrast enhancement.
    2. Background removal with rembg (skipped when the corners are already plain white).
       Stages 1–2 are replaced by an AI edit when the caller passes `ai_edit`.
    3. Autocrop to the subject (alpha bounding box, or the plain border flood fill).
    4. Upscale 2x when the longest side is below a threshold (Real-ESRGAN or Lanczos).
    5. Canvas: scale and center the subject on a fixed-size canvas (colour or transparent),
       or, when the canvas is off, downscale to the resize limits.
    6. Encode in the output format, optionally under a byte limit.

An optional `checkpoint` callback runs between stages so callers can cancel cooperatively.
"""

from __future__ import annotations

import io
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.core import model_store
from app.core.imaging import CONTENT_TYPES, WHITE, ImageFormat, encode, hex_to_rgb, open_image
from app.core.preset_config import BackgroundConfig, CanvasConfig, PresetConfig, ResizeConfig

if TYPE_CHECKING:
    from app.core.esrgan import Upscaler

logger = logging.getLogger(__name__)

Checkpoint = Callable[[], None]
AiEdit = Callable[[Image.Image], Image.Image]

_ALPHA_SUBJECT_THRESHOLD = 10  # alpha above this counts as subject when autocropping


class PresetError(ValueError):
    """The preset cannot be applied to this image (e.g. transparent canvas with JPEG output)."""


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    format: ImageFormat

    @property
    def content_type(self) -> str:
        return CONTENT_TYPES[self.format]


def _no_checkpoint() -> None:
    return None


def _has_transparency(img: Image.Image) -> bool:
    # (min, max) of the 8-bit alpha band: anything but fully opaque everywhere.
    return img.mode == "RGBA" and img.getchannel("A").getextrema() != (255, 255)


def _on_rgb(img: Image.Image, transform: Callable[[Image.Image], Image.Image]) -> Image.Image:
    """Apply an RGB-only transform, carrying the alpha channel (resized if needed) along."""
    if img.mode != "RGBA":
        return transform(img.convert("RGB"))
    result = transform(img.convert("RGB"))
    alpha = img.getchannel("A")
    if alpha.size != result.size:
        alpha = alpha.resize(result.size, Image.Resampling.LANCZOS)
    result.putalpha(alpha)
    return result


# ─── Stages ───────────────────────────────────────────────────────────────────


def enhance_contrast(img: Image.Image, factor: float) -> Image.Image:
    """Boost contrast by `factor` (1.0 = unchanged); transparency is preserved."""
    if factor == 1.0:
        return img
    return _on_rgb(img, lambda rgb: ImageEnhance.Contrast(rgb).enhance(factor))


def is_plain_background(img: Image.Image, threshold: int) -> bool:
    """True if the mean brightness of the four corner patches is at least `threshold`."""
    arr = np.asarray(img.convert("RGB"))
    h, w = arr.shape[:2]
    size = max(5, min(w, h) // 20)
    corners = (arr[:size, :size], arr[:size, -size:], arr[-size:, :size], arr[-size:, -size:])
    return bool(np.mean([c.mean() for c in corners]) >= threshold)


# Loaded background-removal sessions, most recently used last. Two are kept so that alternating
# between two presets (a batch plus the Playground, say) does not reload a model on every switch;
# each one holds hundreds of MB, so the cache stays small.
_REMBG_SESSIONS_KEPT = 2
_rembg_sessions: OrderedDict[str, Any] = OrderedDict()
_rembg_lock = threading.Lock()


def get_rembg_session(model_name: str) -> Any:
    """Return a (cached) rembg session; the model is downloaded into MODELS_DIR on first use.

    Loading is serialized: concurrent first calls would otherwise each download and load the model.
    """
    with _rembg_lock:
        session = _rembg_sessions.get(model_name)
        if session is None:
            model_store.prepare_rembg_home()
            from rembg import new_session  # heavy import (onnxruntime), deferred until first use

            logger.info("Loading rembg model: %s", model_name)
            session = _rembg_sessions[model_name] = new_session(model_name)
            while len(_rembg_sessions) > _REMBG_SESSIONS_KEPT:
                _rembg_sessions.popitem(last=False)
        _rembg_sessions.move_to_end(model_name)
        return session


def remove_background(img: Image.Image, cfg: BackgroundConfig) -> Image.Image:
    """Return an RGBA cutout of the subject."""
    from rembg import remove

    return remove(
        img,
        session=get_rembg_session(cfg.model),
        alpha_matting=cfg.alpha_matting,
        alpha_matting_foreground_threshold=cfg.fg_threshold,
        alpha_matting_background_threshold=cfg.bg_threshold,
        alpha_matting_erode_size=cfg.erode_size,
    ).convert("RGBA")


def _plain_border_mask(img: Image.Image, threshold: int) -> np.ndarray:
    """Subject mask: everything except the near-white region connected to the border.

    Equivalent to a 4-connected flood fill of "white" pixels from every border pixel,
    implemented with OpenCV connected components instead of a Python loop.
    """
    arr = np.asarray(img.convert("RGB"))
    is_white = np.all(arr >= threshold, axis=2)
    _, labels = cv2.connectedComponents(is_white.astype(np.uint8), connectivity=4)
    border = np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    background = np.isin(labels, np.unique(border[border > 0]))
    return ~background


def autocrop(img: Image.Image, padding: int = 4, threshold: int = 230) -> Image.Image:
    """Crop to the subject plus `padding` px.

    Transparent images are cropped to their alpha bounding box; opaque ones to everything
    that is not the plain (near-white) border.
    """
    if _has_transparency(img):
        subject = np.asarray(img.getchannel("A")) > _ALPHA_SUBJECT_THRESHOLD
    else:
        subject = _plain_border_mask(img, threshold)
    rows, cols = np.any(subject, axis=1), np.any(subject, axis=0)
    if not rows.any():
        return img
    top, bottom = np.where(rows)[0][[0, -1]]
    left, right = np.where(cols)[0][[0, -1]]
    return img.crop(
        (
            max(0, int(left) - padding),
            max(0, int(top) - padding),
            min(img.width, int(right) + 1 + padding),
            min(img.height, int(bottom) + 1 + padding),
        )
    )


def is_grayscale(img: Image.Image, threshold: float = 10.0) -> bool:
    """True if the mean channel difference is below `threshold`."""
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return bool(np.mean([np.abs(r - g), np.abs(r - b), np.abs(g - b)]) < threshold)


def _lanczos_2x(rgb: Image.Image) -> Image.Image:
    upscaled = rgb.resize((rgb.width * 2, rgb.height * 2), Image.Resampling.LANCZOS)
    return upscaled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))


def _esrgan_2x(rgb: Image.Image) -> Image.Image:
    if rgb.width * rgb.height > ESRGAN_MAX_INPUT_PIXELS:
        logger.info("Image is %dx%d: too large for Real-ESRGAN on CPU, using Lanczos", rgb.width, rgb.height)
        return _lanczos_2x(rgb)
    upsampler = _get_esrgan()
    if upsampler is None:
        return _lanczos_2x(rgb)
    try:
        # One inference at a time: each run needs about 2 GB and uses every core already.
        with _esrgan_lock:
            upscaled_4x = upsampler.upscale_4x(np.asarray(rgb, dtype=np.uint8))
        # The network only does 4x; halve its output to get the 2x result.
        size = (rgb.width * 2, rgb.height * 2)
        return Image.fromarray(cv2.resize(upscaled_4x, size, interpolation=cv2.INTER_LANCZOS4))
    except Exception as exc:
        logger.warning("ESRGAN upscale failed (%s), falling back to Lanczos", type(exc).__name__)
        return _lanczos_2x(rgb)


def upscale(img: Image.Image, method: str = "esrgan") -> Image.Image:
    """2x upscale. Real-ESRGAN for colour images, Lanczos for grayscale ones or on request."""
    use_esrgan = method == "esrgan" and not is_grayscale(img)
    return _on_rgb(img, _esrgan_2x if use_esrgan else _lanczos_2x)


def place_on_canvas(img: Image.Image, cfg: CanvasConfig) -> Image.Image:
    """Scale the subject to `fill_ratio` of the canvas (aspect kept) and center it."""
    scale = cfg.fill_ratio * min(cfg.width / img.width, cfg.height / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    resized = img.resize(size, Image.Resampling.LANCZOS)
    position = ((cfg.width - size[0]) // 2, (cfg.height - size[1]) // 2)

    if cfg.is_transparent:
        canvas = Image.new("RGBA", (cfg.width, cfg.height), (0, 0, 0, 0))
        canvas.alpha_composite(resized.convert("RGBA"), dest=position)
        return canvas
    canvas = Image.new("RGB", (cfg.width, cfg.height), hex_to_rgb(cfg.background))
    mask = resized.getchannel("A") if resized.mode == "RGBA" else None
    canvas.paste(resized.convert("RGB"), position, mask=mask)
    return canvas


def limit_size(img: Image.Image, cfg: ResizeConfig) -> Image.Image:
    """Downscale (never upscale) to fit the resize limits, keeping the aspect ratio."""
    if cfg.max_width is None and cfg.max_height is None:
        return img
    limited = img.copy()
    limited.thumbnail((cfg.max_width or img.width, cfg.max_height or img.height), Image.Resampling.LANCZOS)
    return limited


def resolve_output_format(config: PresetConfig, source_format: ImageFormat | None) -> ImageFormat:
    """The encoded format: the preset's, or the source's for "keep" (PNG if unknown)."""
    fmt: ImageFormat = (source_format or "png") if config.output.format == "keep" else config.output.format
    if fmt == "jpeg" and config.canvas.enabled and config.canvas.is_transparent:
        raise PresetError("A transparent canvas needs a png or webp output, but this image would be JPEG")
    return fmt


# ─── Real-ESRGAN ──────────────────────────────────────────────────────────────

# The x4 network keeps 64-channel feature maps at 4x the input resolution, so whole-image inference
# needs several GB even for an 800 px image and grows with the pixel count until the process is
# killed. Tiles keep the peak flat (about 2 GB, measured); the padding hides the seams.
ESRGAN_TILE = 192
ESRGAN_TILE_PAD = 10
# CPU time grows with the pixel count (about a minute for 800x600), so larger images use Lanczos.
ESRGAN_MAX_INPUT_PIXELS = 1024 * 1024

_esrgan_lock = threading.Lock()
_esrgan_init_lock = threading.Lock()


class _EsrganState(TypedDict):
    loaded: bool
    upsampler: Upscaler | None


_esrgan_state: _EsrganState = {"loaded": False, "upsampler": None}


def _load_esrgan() -> Upscaler:
    from app.core.esrgan import load_upscaler  # imports torch: only when upscaling is first used

    model_path = model_store.esrgan_weights()
    logger.info("Loading Real-ESRGAN x4plus from %s", model_path)
    return load_upscaler(model_path, tile=ESRGAN_TILE, tile_pad=ESRGAN_TILE_PAD)


def _get_esrgan() -> Upscaler | None:
    """The shared upsampler, or None if it could not be loaded (attempted once per process)."""
    with _esrgan_init_lock:
        if not _esrgan_state["loaded"]:
            _esrgan_state["loaded"] = True
            try:
                _esrgan_state["upsampler"] = _load_esrgan()
            except Exception:
                logger.exception("Real-ESRGAN unavailable; using Lanczos upscaling")
        return _esrgan_state["upsampler"]


# ─── Entry point ──────────────────────────────────────────────────────────────


def process_image(
    raw: bytes,
    config: PresetConfig,
    *,
    source_format: ImageFormat | None,
    ai_edit: AiEdit | None = None,
    checkpoint: Checkpoint | None = None,
) -> ProcessedImage:
    """Run the preset on encoded image bytes and return the encoded result.

    `source_format` is used for output format "keep". Raises `PresetError` when the preset
    cannot be applied and `imaging.ImageTooLarge` when `max_bytes` cannot be met.
    """
    check = checkpoint or _no_checkpoint
    img = open_image(io.BytesIO(raw))
    fmt = resolve_output_format(config, source_format)

    check()
    if ai_edit is not None:
        img = ai_edit(img)
    else:
        if config.contrast.enabled:
            img = enhance_contrast(img, config.contrast.factor)
        check()
        bg = config.background
        if bg.remove and not (bg.skip_if_plain and is_plain_background(img, bg.plain_threshold)):
            img = remove_background(img, bg)

    check()
    if config.autocrop.enabled:
        img = autocrop(img, config.autocrop.padding, config.background.plain_threshold)

    check()
    if config.upscale.enabled and max(img.size) < config.upscale.below_px:
        img = upscale(img, config.upscale.method)

    check()
    img = place_on_canvas(img, config.canvas) if config.canvas.enabled else limit_size(img, config.resize)

    check()
    # A cutout saved as JPEG without a canvas is flattened onto the preset's canvas colour.
    matte = WHITE if config.canvas.is_transparent else hex_to_rgb(config.canvas.background)
    return ProcessedImage(encode(img, fmt, config.output.quality, config.output.max_bytes, matte=matte), fmt)
