"""Small Pillow helpers shared by the pipeline, publishing, imports and the playground.

Output formats are identified by a short name: "jpeg", "png" or "webp".
"""

from __future__ import annotations

import io
from typing import Any, Literal

from PIL import Image

ImageFormat = Literal["jpeg", "png", "webp"]

# File extension → format. Only these extensions can be processed and published.
EXTENSION_FORMATS: dict[str, ImageFormat] = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
CONTENT_TYPES: dict[ImageFormat, str] = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

_PILLOW_FORMATS: dict[ImageFormat, str] = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
_FROM_PILLOW: dict[str, ImageFormat] = {v: k for k, v in _PILLOW_FORMATS.items()}
# Untrusted bytes are only ever handed to these decoders, never to Pillow's other format plugins
# (TIFF, PSD, EPS, ...), which are a much larger attack surface than this app needs.
_DECODERS: tuple[str, ...] = tuple(_PILLOW_FORMATS.values())


class ImageTooLarge(ValueError):
    """The encoded image cannot be brought under the requested byte limit."""


def extension_of(key: str) -> str:
    """Lower-case file extension of a key or filename, without the dot ('' if none)."""
    name = key.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def format_of_extension(ext: str) -> ImageFormat | None:
    return EXTENSION_FORMATS.get(ext.lower())


def format_of_pillow(pillow_format: str | None) -> ImageFormat | None:
    """Our format name for a Pillow `Image.format` value (None if unsupported)."""
    return _FROM_PILLOW.get(pillow_format or "")


def extension_for(fmt: ImageFormat, source_ext: str = "") -> str:
    """File extension for `fmt`, keeping the source's spelling when it is the same format."""
    if format_of_extension(source_ext) == fmt:
        return source_ext.lower()
    return "jpg" if fmt == "jpeg" else fmt


def open_image(buf: io.BytesIO) -> Image.Image:
    """Fully decode `buf` into an RGB or RGBA image (RGBA only when the source has transparency).

    Decoding happens here (not lazily later), so corrupt files and decompression bombs
    raise from this call where the caller's error handling can turn them into a clean failure.
    """
    buf.seek(0)
    with Image.open(buf, formats=_DECODERS) as img:
        img.load()
        has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
        return img.convert("RGBA" if has_alpha else "RGB")


def read_dimensions(buf: io.BytesIO) -> tuple[int, int]:
    """Width and height from the image header (also runs Pillow's decompression-bomb check)."""
    buf.seek(0)
    with Image.open(buf, formats=_DECODERS) as img:
        size = img.size
    buf.seek(0)
    return size


def probe(data: bytes) -> tuple[ImageFormat | None, int, int]:
    """Fully decode `data` and return `(format, width, height)`.

    Raises whatever Pillow raises for undecodable input (including decompression bombs and
    formats other than JPEG, PNG and WebP).
    """
    with Image.open(io.BytesIO(data), formats=_DECODERS) as img:
        img.load()
        return format_of_pillow(img.format), img.width, img.height


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """'#RRGGBB' → (r, g, b)."""
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def flatten(img: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Composite an RGBA image onto an opaque background; other modes are converted to RGB."""
    if img.mode != "RGBA":
        return img.convert("RGB")
    background = Image.new("RGB", img.size, color)
    background.paste(img, mask=img.getchannel("A"))
    return background


def _save(img: Image.Image, fmt: ImageFormat, quality: int, *, fast: bool = False) -> bytes:
    """Encode once. `fast` trades a few percent of size for speed (used while searching for a quality)."""
    per_format: dict[ImageFormat, dict[str, Any]] = {
        "jpeg": {"quality": quality, "optimize": not fast},
        "png": {"optimize": True},
        "webp": {"quality": quality, "method": 4 if fast else 6},
    }
    options = per_format[fmt]
    out = io.BytesIO()
    img.save(out, format=_PILLOW_FORMATS[fmt], **options)
    return out.getvalue()


_MIN_QUALITY = 10
_QUALITY_STEP = 5
WHITE: tuple[int, int, int] = (255, 255, 255)


def _fit_quality(img: Image.Image, fmt: ImageFormat, quality: int, max_bytes: int) -> bytes | None:
    """The highest quality below `quality` (in steps of 5) whose encoding fits, or None.

    Size grows with quality, so a binary search needs about four encodes instead of up to seventeen.
    """
    candidates = list(range(_MIN_QUALITY, min(quality, 90), _QUALITY_STEP))
    best: bytes | None = None
    low, high = 0, len(candidates) - 1
    while low <= high:
        mid = (low + high) // 2
        data = _save(img, fmt, candidates[mid], fast=True)
        if len(data) <= max_bytes:
            best, low = data, mid + 1
        else:
            high = mid - 1
    return best


def encode(
    img: Image.Image,
    fmt: ImageFormat,
    quality: int = 90,
    max_bytes: int | None = None,
    *,
    matte: tuple[int, int, int] = WHITE,
) -> bytes:
    """Encode `img` as `fmt`; JPEG has no transparency, so it is flattened onto `matte`.

    With `max_bytes`, lossy formats are re-encoded at lower quality until they fit.
    Raises `ImageTooLarge` if the limit cannot be met.
    """
    if fmt == "jpeg":
        img = flatten(img, matte)
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    data = _save(img, fmt, quality)
    if max_bytes is None or len(data) <= max_bytes:
        return data
    if fmt != "png":
        fitted = _fit_quality(img, fmt, quality, max_bytes)
        if fitted is not None:
            return fitted
    raise ImageTooLarge(f"Output is {len(data) // 1024} KB, above the {max_bytes // 1024} KB limit")
