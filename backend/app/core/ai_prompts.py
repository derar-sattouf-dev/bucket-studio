"""Shared prompt and error type for the AI image-editing engines (OpenAI, Gemini)."""

from app.core.preset_config import TRANSPARENT


class ImageModelError(RuntimeError):
    """The image model returned no usable image."""


def _color_phrase(background: str) -> str:
    if background == TRANSPARENT or background.upper() == "#FFFFFF":
        return "plain pure white (#FFFFFF)"
    return f"plain solid {background.upper()}"


def default_edit_prompt(background: str = "#FFFFFF") -> str:
    """Instruction used when the preset and the request supply no prompt."""
    return (
        "Isolate the main subject of this image on a clean, "
        f"{_color_phrase(background)} background. "
        "Keep the subject exactly as it is: its shape, proportions, colours, textures and any text "
        "or markings that belong to it. Keep every part of the subject; do not crop or omit anything. "
        "Remove everything else: the original background, surfaces, shadows, reflections, props and "
        "any overlaid watermarks or captions. Center the subject with a small margin around it."
    )
