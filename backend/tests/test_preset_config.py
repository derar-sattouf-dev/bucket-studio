"""PresetConfig validation and the built-in presets."""

import pytest
from pydantic import ValidationError

from app.core.preset_config import SEED_PRESETS, PresetConfig


def test_empty_config_applies_no_step():
    """A config that names no step only re-encodes: nothing from any particular recipe is implied."""
    config = PresetConfig.model_validate({})
    steps = (config.contrast.enabled, config.background.remove, config.autocrop.enabled)
    assert steps == (False, False, False)
    assert (config.upscale.enabled, config.canvas.enabled) == (False, False)
    assert (config.resize.max_width, config.resize.max_height) == (None, None)
    assert config.output.format == "keep"
    assert config.ai.engine == "none"


def test_partial_sections_are_filled_from_defaults():
    config = PresetConfig.model_validate({"canvas": {"width": 640}, "output": {"format": "webp"}})
    assert (config.canvas.width, config.canvas.height) == (640, 1000)
    assert config.canvas.fill_ratio == 0.85
    assert config.output.quality == 90


@pytest.mark.parametrize(
    "payload",
    [
        {"contrast": {"factor": 3}},
        {
            "canvas": {"width": 8},
        },
        {"canvas": {"fill_ratio": 0}},
        {"canvas": {"background": "white"}},
        {"canvas": {"background": "#FFF"}},
        {"output": {"quality": 100}},
        {"output": {"max_bytes": 1000}},
        {"output": {"format": "gif"}},
        {"background": {"model": "../../evil"}},
        {"upscale": {"method": "bicubic"}},
        {"ai": {"engine": "claude"}},
        {"ai": {"prompt": "x" * 4001}},
        {"autocrop": {"padding": -1}},
        {"unknown_stage": {}},
        {"canvas": {"widht": 500}},
    ],
)
def test_invalid_configs_are_rejected(payload):
    with pytest.raises(ValidationError):
        PresetConfig.model_validate(payload)


def test_transparent_canvas_requires_alpha_capable_format():
    with pytest.raises(ValidationError, match="transparent canvas"):
        PresetConfig.model_validate(
            {"canvas": {"enabled": True, "background": "transparent"}, "output": {"format": "jpeg"}}
        )
    for fmt in ("png", "webp", "keep"):
        PresetConfig.model_validate(
            {"canvas": {"enabled": True, "background": "transparent"}, "output": {"format": fmt}}
        )
    # Without a canvas the background colour is irrelevant.
    PresetConfig.model_validate(
        {"canvas": {"enabled": False, "background": "transparent"}, "output": {"format": "jpeg"}}
    )


def test_seed_presets():
    names = [name for name, _, _ in SEED_PRESETS]
    assert names == ["White background (square)", "Transparent cutout", "Upscale only", "Web optimize"]
    white, cutout, upscale_only, web = (config for _, _, config in SEED_PRESETS)
    assert white.output.format == "keep" and white.canvas.enabled and white.canvas.background == "#FFFFFF"
    assert cutout.output.format == "png" and not cutout.canvas.enabled and cutout.autocrop.padding == 8
    assert not upscale_only.background.remove and upscale_only.upscale.below_px == 1600
    assert web.output.format == "webp" and web.output.max_bytes == 512_000 and web.resize.max_width == 2000


def test_the_default_seed_spells_out_its_whole_recipe():
    """The white-square recipe lives in the seed, not in the model's defaults."""
    name, _, config = SEED_PRESETS[0]
    assert name == "White background (square)"
    assert (config.background.remove, config.background.skip_if_plain, config.autocrop.enabled) == (True, True, True)
    assert (config.upscale.enabled, config.upscale.below_px) == (True, 800)
    assert (config.canvas.enabled, config.canvas.width, config.canvas.height) == (True, 1000, 1000)
    assert (config.canvas.background, config.output.format) == ("#FFFFFF", "keep")
