"""Publish derivatives: extra files rendered next to a published image (thumbnails, WebP copies…).

A derivative is described by a name template plus size/format options. Templates may only
use `{stem}` and `{ext}` (of the source file name) and safe file-name characters, so a
derivative always lands in the source image's own folder and can never escape it.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.imaging import CONTENT_TYPES, ImageFormat, encode, extension_of, open_image

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_LITERAL = re.compile(r"^[A-Za-z0-9._-]*$")
_PLACEHOLDERS = frozenset({"stem", "ext"})
_FORMAT_SUFFIXES: dict[str, tuple[str, ...]] = {
    "same": (".{ext}",),
    "jpeg": (".jpg", ".jpeg"),
    "png": (".png",),
    "webp": (".webp",),
}
MAX_DERIVATIVES = 10


class DerivativeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    width: int | None = Field(None, ge=16, le=4000)
    height: int | None = Field(None, ge=16, le=4000)
    # contain: fit inside the box, never upscaled; cover: fill the box exactly, center-cropped
    fit: Literal["contain", "cover"] = "contain"
    format: Literal["same", "jpeg", "png", "webp"] = "same"
    quality: int = Field(85, ge=1, le=95)

    @field_validator("name")
    @classmethod
    def _safe_template(cls, name: str) -> str:
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError("name must not contain '/', '\\' or '..'")
        placeholders = _PLACEHOLDER.findall(name)
        if any(p not in _PLACEHOLDERS for p in placeholders):
            raise ValueError("name may only use the {stem} and {ext} placeholders")
        if not _LITERAL.match(_PLACEHOLDER.sub("", name)):
            raise ValueError("name may only contain letters, digits, '.', '_', '-' and placeholders")
        if "stem" not in placeholders:
            raise ValueError("name must contain {stem} so derivatives of different images cannot collide")
        if name.startswith("."):
            raise ValueError("name must not start with '.'")
        return name

    @model_validator(mode="after")
    def _consistent(self) -> DerivativeSpec:
        suffixes = _FORMAT_SUFFIXES[self.format]
        if not self.name.lower().endswith(suffixes):
            raise ValueError(f"name must end with {' or '.join(suffixes)} for format '{self.format}'")
        if self.fit == "cover" and (self.width is None or self.height is None):
            raise ValueError("fit 'cover' needs both width and height")
        return self


class PublishConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Empty by default: publishing writes no extra files, and no file names are hidden from sync,
    # until an admin adds a derivative.
    derivatives: list[DerivativeSpec] = Field(default_factory=list, max_length=MAX_DERIVATIVES)

    @field_validator("derivatives")
    @classmethod
    def _unique_names(cls, derivatives: list[DerivativeSpec]) -> list[DerivativeSpec]:
        names = [d.name.lower() for d in derivatives]
        if len(set(names)) != len(names):
            raise ValueError("derivative names must be unique")
        return derivatives


def render_name(template: str, source_key: str) -> str:
    """File name of a derivative for `source_key`, e.g. '{stem}_thumb.{ext}' → 'photo_thumb.jpg'."""
    filename = source_key.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return template.replace("{stem}", stem).replace("{ext}", extension_of(filename))


def derivative_key(source_key: str, spec: DerivativeSpec) -> str:
    folder = source_key.rsplit("/", 1)[0] + "/" if "/" in source_key else ""
    return folder + render_name(spec.name, source_key)


def name_glob(template: str) -> str:
    """fnmatch pattern matching every file a template can produce ('{stem}_thumb.{ext}' → '*_thumb.*')."""
    return template.replace("{stem}", "*").replace("{ext}", "*")


def check_names_against_sources(publish: PublishConfig, extensions: Iterable[str]) -> None:
    """Reject templates that would overwrite the source itself (e.g. '{stem}.webp' for .webp sources)."""
    for spec in publish.derivatives:
        for ext in extensions:
            if render_name(spec.name, f"x.{ext}") == f"x.{ext}":
                raise ValueError(f"Derivative '{spec.name}' would overwrite .{ext} source images")


def derivative_format(spec: DerivativeSpec, source_format: ImageFormat) -> ImageFormat:
    return source_format if spec.format == "same" else spec.format


def _resize(img: Image.Image, spec: DerivativeSpec) -> Image.Image:
    if spec.width is None and spec.height is None:
        return img
    if spec.fit == "cover":
        # `cover` always has both sides (validated on the spec); the fallbacks only satisfy the type.
        return ImageOps.fit(img, (spec.width or img.width, spec.height or img.height), Image.Resampling.LANCZOS)
    contained = img.copy()
    contained.thumbnail((spec.width or img.width, spec.height or img.height), Image.Resampling.LANCZOS)
    return contained


def render_derivative(data: bytes, spec: DerivativeSpec, source_format: ImageFormat) -> bytes:
    """Encode one derivative of the image `data` (whose format is `source_format`)."""
    img = _resize(open_image(io.BytesIO(data)), spec)
    return encode(img, derivative_format(spec, source_format), spec.quality)


@dataclass(frozen=True)
class RenderedDerivative:
    key: str
    data: bytes
    content_type: str


def render_all(
    data: bytes, publish: PublishConfig, source_key: str, source_format: ImageFormat
) -> list[RenderedDerivative]:
    """Render every configured derivative of the image published (or restored) at `source_key`."""
    rendered = []
    for spec in publish.derivatives:
        key = derivative_key(source_key, spec)
        if key == source_key:
            raise ValueError(f"Derivative '{spec.name}' would overwrite the source image")
        fmt = derivative_format(spec, source_format)
        rendered.append(RenderedDerivative(key, render_derivative(data, spec, source_format), CONTENT_TYPES[fmt]))
    return rendered
