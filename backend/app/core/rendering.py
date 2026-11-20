"""Render one image with a preset: pick the engine (local or AI), then run the pipeline.

Engine choices (`EngineChoice`), as accepted by the API:

* "preset" — follow the preset's `ai` rule (AI only for images below `ai.below_px`, or always when 0);
* "local"  — always the local pipeline, whatever the preset says;
* "openai" / "gemini" — always that model.

Shared by stored-image processing (`image_pipeline`) and the playground.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Literal

from PIL import Image

from app.config import settings
from app.core.ai_prompts import default_edit_prompt
from app.core.imaging import ImageFormat, open_image, read_dimensions
from app.core.preset_config import AiConfig, AiImageSize, PresetConfig
from app.core.processor import AiEdit, Checkpoint, ProcessedImage, process_image

logger = logging.getLogger(__name__)

EngineChoice = Literal["preset", "local", "openai", "gemini"]
Engine = Literal["local", "openai", "gemini"]


class EngineUnavailable(Exception):
    """The requested AI engine has no API key configured; the message is safe to show."""


@dataclass(frozen=True)
class AiModels:
    """Model ids for the AI engines (runtime settings)."""

    openai: str
    gemini: str


@dataclass(frozen=True)
class RenderedImage:
    image: ProcessedImage
    processed_by: str  # "local", "openai:<model>" or "gemini:<model>"
    source_width: int
    source_height: int


def is_engine_configured(engine: Engine) -> bool:
    if engine == "openai":
        return bool(settings.openai_api_key)
    if engine == "gemini":
        return bool(settings.gemini_api_key)
    return True


def ensure_engine_available(choice: EngineChoice, config: PresetConfig) -> None:
    """Fail fast when the request (or the preset's AI rule) needs an engine without an API key."""
    engine: Engine | None
    if choice == "preset":
        engine = None if config.ai.engine == "none" else config.ai.engine
    elif choice == "local":
        engine = None
    else:
        engine = choice
    if engine is not None and not is_engine_configured(engine):
        raise EngineUnavailable(f"The {engine} engine is not configured on the server (missing API key)")


def resolve_engine(choice: EngineChoice, ai: AiConfig, width: int, height: int) -> Engine:
    if choice != "preset":
        return choice
    if ai.engine == "none" or (ai.below_px and max(width, height) >= ai.below_px):
        return "local"
    return ai.engine


def engine_label(engine: Engine, models: AiModels) -> str:
    if engine == "openai":
        return f"openai:{models.openai}"
    if engine == "gemini":
        return f"gemini:{models.gemini}"
    return "local"


def _ai_edit(engine: Engine, prompt: str, size: AiImageSize, models: AiModels) -> AiEdit:
    def run(img: Image.Image) -> Image.Image:
        if engine == "openai":
            from app.core.gpt_image import edit_with_openai

            data = edit_with_openai(img, prompt, models.openai, size)
        else:
            from app.core.gemini_image import edit_with_gemini

            data = edit_with_gemini(img, prompt, models.gemini)
        return open_image(io.BytesIO(data))

    return run


def render(
    raw: bytes,
    config: PresetConfig,
    *,
    source_format: ImageFormat | None,
    ai_models: AiModels,
    choice: EngineChoice = "preset",
    prompt: str | None = None,
    checkpoint: Checkpoint | None = None,
) -> RenderedImage:
    """Process encoded image bytes with `config`. Blocking: run it in a worker thread."""
    width, height = read_dimensions(io.BytesIO(raw))
    engine = resolve_engine(choice, config.ai, width, height)
    ai_edit = None
    if engine != "local":
        logger.info("Rendering a %dx%d image with %s", width, height, engine)
        text = prompt or config.ai.prompt or default_edit_prompt(config.canvas.background)
        ai_edit = _ai_edit(engine, text, config.ai.size, ai_models)
    image = process_image(raw, config, source_format=source_format, ai_edit=ai_edit, checkpoint=checkpoint)
    return RenderedImage(image, engine_label(engine, ai_models), width, height)
