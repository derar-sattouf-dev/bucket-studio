"""Image editing with Gemini image generation (google-genai SDK; blocking, call from a worker thread).

Returns the raw image produced by the model; the caller continues the preset pipeline.
"""

import io
import logging
from functools import lru_cache

from google import genai
from google.genai import types
from PIL import Image

from app.config import settings
from app.core.ai_prompts import ImageModelError

logger = logging.getLogger(__name__)

_GENERATE_CONFIG = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.gemini_api_key)


def _encode_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def edit_with_gemini(img: Image.Image, prompt: str, model: str) -> bytes:
    """Send `img` with `prompt` to the Gemini image `model`; returns the result bytes."""
    contents: list[types.PartUnionDict] = [
        prompt,
        types.Part.from_bytes(data=_encode_jpeg(img), mime_type="image/jpeg"),
    ]
    response = _get_client().models.generate_content(
        model=model,
        contents=contents,
        config=_GENERATE_CONFIG,
    )
    candidates = response.candidates or []
    parts = (candidates[0].content.parts or []) if candidates and candidates[0].content else []
    for part in parts:
        if part.inline_data is not None and part.inline_data.data:
            data = part.inline_data.data
            logger.info("[gemini-image] edited image (%d KB)", len(data) // 1024)
            return data
    # The text part usually explains a refusal; keep it server-side only.
    logger.warning("[gemini-image] no image returned: %.300r", response.text)
    raise ImageModelError("The image model returned no image")
