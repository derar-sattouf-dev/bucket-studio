"""Source filters, automatic derivative exclusion and folder grouping."""

import pytest
from pydantic import ValidationError

from app.core.derivatives import PublishConfig
from app.core.source_filters import SourceFilters, SourceMatcher, group_key_of


def _matcher(filters: dict | None = None, derivatives: list | None = None) -> SourceMatcher:
    publish = PublishConfig() if derivatives is None else PublishConfig.model_validate({"derivatives": derivatives})
    return SourceMatcher(SourceFilters.model_validate(filters or {}), publish)


def test_extensions_and_globs():
    matcher = _matcher({"extensions": ["JPG", ".png", "jpg"], "exclude_globs": ["draft-*", "*.tmp.*"]})
    assert matcher.matches("images/a/photo.jpg")
    assert matcher.matches("images/a/PHOTO.JPG")
    assert matcher.matches("images/a/photo.png")
    assert not matcher.matches("images/a/photo.webp")
    assert not matcher.matches("images/a/photo.jpeg")
    assert not matcher.matches("images/a/Draft-1.jpg")
    assert not matcher.matches("images/a/x.tmp.png")
    assert not matcher.matches("images/a/noext")


def test_derivatives_are_always_excluded():
    matcher = _matcher(derivatives=[{"name": "{stem}_thumb.{ext}"}, {"name": "{stem}-md.webp", "format": "webp"}])
    assert matcher.matches("images/a/photo.jpg")
    assert not matcher.matches("images/a/photo_thumb.jpg")
    assert not matcher.matches("images/a/photo-md.webp")
    assert matcher.matches("images/a/photo.webp")  # not hard-coded any more


def test_filter_validation():
    SourceFilters.model_validate({"extensions": ["webp"]})
    for payload in ({"extensions": []}, {"extensions": ["gif"]}, {"exclude_globs": ["a/b*"]}):
        with pytest.raises(ValidationError):
            SourceFilters.model_validate(payload)


@pytest.mark.parametrize(
    ("key", "depth", "expected"),
    [
        ("images/a/b/c/x.jpg", 0, None),
        ("images/a/b/c/x.jpg", 1, "a"),
        ("images/a/b/c/x.jpg", 2, "a/b"),
        ("images/a/b/c/x.jpg", 5, "a/b/c"),
        ("images/x.jpg", 1, None),
        ("elsewhere/a/x.jpg", 1, None),
    ],
)
def test_group_key_of(key, depth, expected):
    assert group_key_of(key, "images/", depth) == expected
