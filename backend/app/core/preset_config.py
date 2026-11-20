"""Preset configuration: the validated description of how an image is processed.

Every field has a default, so partial configs are filled in. Unknown keys are rejected
(a typo must not silently fall back to a default).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RembgModel = Literal[
    "birefnet-general",
    "birefnet-general-lite",
    "birefnet-massive",
    "isnet-general-use",
    "u2net",
    "u2netp",
    "silueta",
]
AiEngine = Literal["none", "openai", "gemini"]
AiImageSize = Literal["auto", "1024x1024", "1024x1536", "1536x1024"]
OutputFormat = Literal["keep", "jpeg", "png", "webp"]

TRANSPARENT = "transparent"
MAX_PROMPT_LENGTH = 4000
Dimension = Annotated[int, Field(ge=16, le=8000)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContrastConfig(_Section):
    enabled: bool = False
    factor: float = Field(1.1, ge=0.5, le=2.0)


class BackgroundConfig(_Section):
    remove: bool = False
    model: RembgModel = "birefnet-general"
    skip_if_plain: bool = False  # skip removal when the corners are already near-white
    plain_threshold: int = Field(230, ge=0, le=255)
    alpha_matting: bool = False
    fg_threshold: int = Field(240, ge=0, le=255)
    bg_threshold: int = Field(10, ge=0, le=255)
    erode_size: int = Field(10, ge=0, le=100)


class AutocropConfig(_Section):
    enabled: bool = False
    padding: int = Field(4, ge=0, le=200)


class UpscaleConfig(_Section):
    enabled: bool = False
    below_px: int = Field(800, ge=1, le=4000)  # upscale 2x when the longest side is smaller
    method: Literal["esrgan", "lanczos"] = "esrgan"


class CanvasConfig(_Section):
    enabled: bool = False
    width: Dimension = 1000
    height: Dimension = 1000
    fill_ratio: float = Field(0.85, ge=0.1, le=1.0)
    background: str = Field("#FFFFFF", pattern=r"^(#[0-9A-Fa-f]{6}|transparent)$")

    @property
    def is_transparent(self) -> bool:
        return self.background == TRANSPARENT


class ResizeConfig(_Section):
    """Downscale limits, applied when the canvas is disabled. None = no limit."""

    max_width: Dimension | None = None
    max_height: Dimension | None = None


class OutputConfig(_Section):
    format: OutputFormat = "keep"
    quality: int = Field(90, ge=1, le=95)
    max_bytes: int | None = Field(None, ge=10_240, le=100 * 1024 * 1024)


class AiConfig(_Section):
    """Regenerate with an AI model instead of local background removal.

    Applies when `engine` is set and the longest side is below `below_px` (0 = always).
    """

    engine: AiEngine = "none"
    below_px: int = Field(0, ge=0, le=8000)
    prompt: str | None = Field(None, min_length=1, max_length=MAX_PROMPT_LENGTH)
    size: AiImageSize = "auto"


class PresetConfig(_Section):
    """One processing recipe. Every step is off by default: a config that names no step changes
    nothing but the encoding, so a partial config never applies a step the author did not ask for.
    The numbers on the sections are only starting values for when a step is switched on."""

    contrast: ContrastConfig = Field(default_factory=ContrastConfig)
    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    autocrop: AutocropConfig = Field(default_factory=AutocropConfig)
    upscale: UpscaleConfig = Field(default_factory=UpscaleConfig)
    canvas: CanvasConfig = Field(default_factory=CanvasConfig)
    resize: ResizeConfig = Field(default_factory=ResizeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    ai: AiConfig = Field(default_factory=AiConfig)

    @model_validator(mode="after")
    def _transparent_needs_alpha_format(self) -> PresetConfig:
        if self.canvas.enabled and self.canvas.is_transparent and self.output.format == "jpeg":
            raise ValueError("A transparent canvas needs output format png, webp or keep")
        return self


@dataclass(frozen=True)
class ResolvedPreset:
    """A preset snapshot used for one processing request or job."""

    id: int
    name: str
    config: PresetConfig


SEED_PRESETS: list[tuple[str, str, PresetConfig]] = [
    (
        "White background (square)",
        "Remove the background and center the subject on a 1000×1000 white square (keeps the source format).",
        PresetConfig(
            background=BackgroundConfig(remove=True, skip_if_plain=True),
            autocrop=AutocropConfig(enabled=True),
            upscale=UpscaleConfig(enabled=True, below_px=800),
            canvas=CanvasConfig(enabled=True, width=1000, height=1000, fill_ratio=0.85, background="#FFFFFF"),
            output=OutputConfig(format="keep", quality=90),
        ),
    ),
    (
        "Transparent cutout",
        "Remove the background and crop to the subject, keeping transparency (PNG).",
        PresetConfig(
            background=BackgroundConfig(remove=True),
            autocrop=AutocropConfig(enabled=True, padding=8),
            upscale=UpscaleConfig(enabled=True, below_px=800),
            output=OutputConfig(format="png"),
        ),
    ),
    (
        "Upscale only",
        "Upscale images smaller than 1600 px with Real-ESRGAN; nothing else changes.",
        PresetConfig(upscale=UpscaleConfig(enabled=True, below_px=1600)),
    ),
    (
        "Web optimize",
        "Downscale to at most 2000×2000 and encode as WebP under 500 KB.",
        PresetConfig(
            resize=ResizeConfig(max_width=2000, max_height=2000),
            output=OutputConfig(format="webp", quality=82, max_bytes=512_000),
        ),
    ),
]
