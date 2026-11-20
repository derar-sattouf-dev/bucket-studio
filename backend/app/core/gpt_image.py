"""Image editing with the OpenAI image API (blocking; call from a worker thread).

Returns the raw image produced by the model; the caller continues the preset pipeline.
"""

import base64
import io
import logging
from functools import lru_cache

from openai import OpenAI
from PIL import Image

from app.config import settings
from app.core.ai_prompts import ImageModelError
from app.core.preset_config import AiImageSize

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 180.0


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key, timeout=_REQUEST_TIMEOUT_SECONDS)


def _encode_webp(img: Image.Image) -> io.BytesIO:
    """The edit endpoint accepts PNG/WebP but not JPEG."""
    out = io.BytesIO()
    img.convert("RGBA").save(out, format="WEBP", quality=90)
    out.seek(0)
    return out


def edit_with_openai(img: Image.Image, prompt: str, model: str, size: AiImageSize = "auto") -> bytes:
    """Send `img` with `prompt` to the OpenAI image `model`; returns the result bytes."""
    response = _get_client().images.edit(
        model=model,
        image=("image.webp", _encode_webp(img), "image/webp"),
        prompt=prompt,
        size=size,
    )
    if not response.data or not response.data[0].b64_json:
        raise ImageModelError("The image model returned no image")
    data = base64.b64decode(response.data[0].b64_json)
    logger.info("[openai-image] edited image (%d KB)", len(data) // 1024)
    return data
