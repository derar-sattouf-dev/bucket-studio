"""Local pipeline stages with background removal off (no model download, no network)."""

import io

import pytest
from PIL import Image

from app.core.imaging import ImageTooLarge, encode, open_image
from app.core.preset_config import PresetConfig
from app.core.processor import PresetError, autocrop, place_on_canvas, process_image
from tests.conftest import make_image

# Every step these tests exercise is switched on explicitly (all steps are off by default);
# background removal stays off and upscaling uses Lanczos, so no ML model is needed.
NO_MODELS = {
    "background": {"remove": False},
    "autocrop": {"enabled": True},
    "upscale": {"enabled": True, "method": "lanczos"},
    "canvas": {"enabled": True},
}


def _config(**sections) -> PresetConfig:
    merged = {name: {**NO_MODELS.get(name, {}), **values} for name, values in sections.items()}
    return PresetConfig.model_validate({**NO_MODELS, **merged})


def _decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def test_autocrop_on_white_border():
    img = open_image(io.BytesIO(make_image((100, 80), margin=20)))
    cropped = autocrop(img, padding=2)
    assert cropped.size == (64, 44)


def test_autocrop_uses_alpha_bounding_box():
    img = open_image(io.BytesIO(make_image((100, 80), color=(10, 10, 10, 255), background=None, margin=30)))
    assert img.mode == "RGBA"
    assert autocrop(img, padding=0).size == (40, 20)


def test_canvas_fill_ratio_and_size():
    img = Image.new("RGB", (200, 100), (0, 0, 255))
    canvas = place_on_canvas(img, _config(canvas={"width": 300, "height": 200, "fill_ratio": 0.5}).canvas)
    assert canvas.size == (300, 200)
    assert canvas.mode == "RGB"
    assert canvas.getpixel((0, 0)) == (255, 255, 255)
    assert canvas.getpixel((150, 100)) == (0, 0, 255)


def test_pipeline_white_square_jpeg():
    config = _config(canvas={"width": 256, "height": 256}, output={"format": "jpeg", "quality": 80})
    result = process_image(make_image((120, 60)), config, source_format="png")
    assert result.format == "jpeg" and result.content_type == "image/jpeg"
    out = _decode(result.data)
    assert (out.format, out.size) == ("JPEG", (256, 256))


def test_transparent_canvas_produces_png_with_alpha():
    config = _config(canvas={"width": 128, "height": 128, "background": "transparent"}, output={"format": "png"})
    source = make_image((90, 60), color=(0, 128, 0, 255), background=None, margin=10)
    result = process_image(source, config, source_format="png")
    out = _decode(result.data)
    assert (out.format, out.mode, out.size) == ("PNG", "RGBA", (128, 128))
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((64, 64))[3] == 255


def test_transparent_canvas_with_keep_on_jpeg_source_fails_clearly():
    config = _config(canvas={"background": "transparent"}, output={"format": "keep"})
    with pytest.raises(PresetError):
        process_image(make_image(fmt="JPEG"), config, source_format="jpeg")


def test_keep_format_and_resize_without_canvas():
    config = _config(
        autocrop={"enabled": False},
        upscale={"enabled": False},
        canvas={"enabled": False},
        resize={"max_width": 50},
    )
    result = process_image(make_image((200, 100), fmt="WEBP"), config, source_format="webp")
    out = _decode(result.data)
    assert (result.format, out.size) == ("webp", (50, 25))


def test_upscale_doubles_small_images():
    config = _config(autocrop={"enabled": False}, canvas={"enabled": False}, upscale={"below_px": 500})
    out = _decode(process_image(make_image((100, 50)), config, source_format="png").data)
    assert out.size == (200, 100)


def test_contrast_keeps_transparency():
    config = _config(
        contrast={"enabled": True, "factor": 1.5},
        autocrop={"enabled": False},
        upscale={"enabled": False},
        canvas={"enabled": False},
    )
    source = make_image((40, 40), color=(100, 100, 100, 255), background=None, margin=10)
    out = _decode(process_image(source, config, source_format="png").data)
    assert out.mode == "RGBA" and out.getpixel((0, 0))[3] == 0


def test_checkpoint_runs_between_stages():
    calls: list[int] = []
    process_image(make_image(), _config(), source_format="png", checkpoint=lambda: calls.append(1))
    assert len(calls) >= 5


def test_max_bytes_is_enforced():
    noisy = Image.effect_noise((600, 600), 100).convert("RGB")
    with pytest.raises(ImageTooLarge):
        encode(noisy, "png", max_bytes=10_240)
    assert len(encode(noisy, "jpeg", quality=90, max_bytes=150_000)) <= 150_000
