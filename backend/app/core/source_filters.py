"""Which bucket objects are source images, and how they are grouped.

A key is a source image when its extension is allowed, its file name matches no exclude
glob, and it is not a publish derivative (every derivative name pattern is excluded
automatically, so published thumbnails are never synced back in as sources).
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.derivatives import PublishConfig, name_glob
from app.core.imaging import extension_of

SourceExtension = Literal["jpg", "jpeg", "png", "webp"]
ExcludeGlob = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[^/\\]+$")]


def _default_extensions() -> list[SourceExtension]:
    return ["jpg", "jpeg", "png", "webp"]


class SourceFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extensions: list[SourceExtension] = Field(default_factory=_default_extensions, min_length=1, max_length=4)
    exclude_globs: list[ExcludeGlob] = Field(default_factory=list, max_length=50)

    @field_validator("extensions", mode="before")
    @classmethod
    def _normalise_extensions(cls, value: object) -> object:
        if isinstance(value, list):
            normalised = [v.lower().lstrip(".") if isinstance(v, str) else v for v in value]
            return list(dict.fromkeys(normalised))
        return value


class SourceMatcher:
    """Decides whether a key is a source image under the current filters and publish settings."""

    def __init__(self, filters: SourceFilters, publish: PublishConfig) -> None:
        self._extensions = frozenset(filters.extensions)
        self._globs = tuple(
            g.lower() for g in (*filters.exclude_globs, *(name_glob(d.name) for d in publish.derivatives))
        )

    def matches(self, key: str) -> bool:
        name = key.rsplit("/", 1)[-1]
        if extension_of(name) not in self._extensions:
            return False
        lowered = name.lower()
        return not any(fnmatchcase(lowered, glob) for glob in self._globs)


def group_key_of(source_key: str, source_prefix: str, depth: int) -> str | None:
    """The first `depth` folders after `source_prefix`, e.g. depth 1: 'images/a/b/x.jpg' → 'a'.

    None when grouping is off (depth 0), the key is outside the prefix, or the file sits
    directly under the prefix.
    """
    if depth <= 0 or not source_key.startswith(source_prefix):
        return None
    folders = source_key[len(source_prefix) :].split("/")[:-1]
    return "/".join(folders[:depth]) or None
