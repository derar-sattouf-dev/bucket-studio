"""Publish derivative templates: strict validation, naming and rendering."""

import io

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.derivatives import (
    DerivativeSpec,
    PublishConfig,
    check_names_against_sources,
    derivative_key,
    name_glob,
    render_all,
    render_derivative,
    render_name,
)
from tests.conftest import make_image


@pytest.mark.parametrize(
    "name",
    [
        "thumbs/{stem}.{ext}",  # no folders
        "..{stem}.{ext}",
        "{stem}..{ext}",
        "{stem}\\x.{ext}",
        "{stem}_{size}.{ext}",  # unknown placeholder
        "{stem} copy.{ext}",  # space
        "{stem}_{.{ext}",
        "thumb.{ext}",  # no {stem}: derivatives of two images would collide
        ".{stem}.{ext}",
        "{stem}_thumb.jpg",  # format "same" must keep the source extension
    ],
)
def test_unsafe_or_inconsistent_names_are_rejected(name):
    with pytest.raises(ValidationError):
        DerivativeSpec(name=name)


def test_name_must_match_format():
    DerivativeSpec(name="{stem}.webp", format="webp")
    DerivativeSpec(name="{stem}_small.jpeg", format="jpeg")
    with pytest.raises(ValidationError):
        DerivativeSpec(name="{stem}.png", format="webp")


def test_cover_needs_both_dimensions():
    with pytest.raises(ValidationError):
        DerivativeSpec(name="{stem}_sq.{ext}", width=100, fit="cover")


def test_names_must_be_unique():
    spec = {"name": "{stem}_t.{ext}"}
    with pytest.raises(ValidationError, match="unique"):
        PublishConfig.model_validate({"derivatives": [spec, spec]})


def test_no_derivatives_are_written_unless_configured():
    assert PublishConfig().derivatives == []


def test_rendering_names_and_keys():
    spec = DerivativeSpec(name="{stem}_thumb.{ext}")
    assert render_name(spec.name, "images/a/photo.final.JPG") == "photo.final_thumb.jpg"
    assert derivative_key("images/a/photo.png", spec) == "images/a/photo_thumb.png"
    assert name_glob(spec.name) == "*_thumb.*"


def test_derivative_that_would_overwrite_its_source_is_rejected():
    webp_copy = PublishConfig.model_validate({"derivatives": [{"name": "{stem}.webp", "format": "webp"}]})
    with pytest.raises(ValueError, match="overwrite"):
        check_names_against_sources(webp_copy, ["jpg", "webp"])
    check_names_against_sources(webp_copy, ["jpg", "png"])


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_contain_never_upscales_and_cover_fills_the_box():
    source = make_image((400, 200))
    contain = DerivativeSpec(name="{stem}_c.{ext}", width=100, height=100)
    cover = DerivativeSpec(name="{stem}_v.{ext}", width=100, height=100, fit="cover")
    width_only = DerivativeSpec(name="{stem}_w.{ext}", width=1000)
    assert _size(render_derivative(source, contain, "png")) == (100, 50)
    assert _size(render_derivative(source, cover, "png")) == (100, 100)
    assert _size(render_derivative(source, width_only, "png")) == (400, 200)


def test_render_all_formats_and_content_types():
    publish = PublishConfig.model_validate(
        {"derivatives": [{"name": "{stem}_thumb.{ext}", "width": 50}, {"name": "{stem}.webp", "format": "webp"}]}
    )
    thumb, webp = render_all(make_image(fmt="JPEG"), publish, "images/x/a.jpg", "jpeg")
    assert (thumb.key, thumb.content_type) == ("images/x/a_thumb.jpg", "image/jpeg")
    assert (webp.key, webp.content_type) == ("images/x/a.webp", "image/webp")
    assert Image.open(io.BytesIO(webp.data)).format == "WEBP"
