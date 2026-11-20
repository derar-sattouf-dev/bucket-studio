"""Preset use cases: CRUD, the single-default rule and first-start seeding.

Invariant: whenever at least one preset exists, exactly one is the default. The default
cannot be deleted; switching the default is a single transaction.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.preset_config import SEED_PRESETS, PresetConfig, ResolvedPreset
from app.db import crud
from app.db.models import Preset
from app.services.settings_service import invalidate_settings_cache

logger = logging.getLogger(__name__)


class PresetNotFound(Exception):
    pass


class PresetConflict(Exception):
    """Name already taken or the operation would break the default rule; the message is safe to show."""


def config_of(preset: Preset) -> PresetConfig:
    """Parse a stored config; stored configs were validated on write, so this only fails on tampering."""
    return PresetConfig.model_validate_json(preset.config)


def _serialize(config: PresetConfig) -> str:
    return config.model_dump_json()


async def seed_presets(db: AsyncSession) -> int:
    """Insert the built-in presets when the table is empty; the first one becomes the default."""
    if await crud.count_presets(db):
        return 0
    for index, (name, description, config) in enumerate(SEED_PRESETS):
        db.add(Preset(name=name, description=description, config=_serialize(config), is_default=index == 0))
    await db.commit()
    invalidate_settings_cache()
    logger.info("[presets] Seeded %d built-in presets", len(SEED_PRESETS))
    return len(SEED_PRESETS)


async def _require(db: AsyncSession, preset_id: int) -> Preset:
    preset = await crud.get_preset(db, preset_id)
    if preset is None:
        raise PresetNotFound(preset_id)
    return preset


async def resolve_preset(db: AsyncSession, preset_id: int | None) -> ResolvedPreset:
    """The requested preset, or the default one when `preset_id` is None."""
    preset = await (crud.get_default_preset(db) if preset_id is None else crud.get_preset(db, preset_id))
    if preset is None:
        raise PresetNotFound(preset_id)
    try:
        return ResolvedPreset(preset.id, preset.name, config_of(preset))
    except ValidationError as exc:
        logger.error("Stored config of preset %d is invalid", preset.id)
        raise PresetConflict(f"Preset '{preset.name}' has an invalid stored config") from exc


async def _commit_or_conflict(db: AsyncSession, name: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise PresetConflict(f"A preset named '{name}' already exists") from exc


async def create_preset(db: AsyncSession, *, name: str, description: str, config: PresetConfig, actor: str) -> Preset:
    if await crud.get_preset_by_name(db, name):
        raise PresetConflict(f"A preset named '{name}' already exists")
    is_first = await crud.count_presets(db) == 0
    preset = Preset(name=name, description=description, config=_serialize(config), is_default=is_first)
    db.add(preset)
    await _commit_or_conflict(db, name)
    await db.refresh(preset)
    if is_first:
        invalidate_settings_cache()
    await crud.log_activity(
        db, "preset.created", f"{actor} created preset '{preset.name}'", {"id": preset.id}, username=actor
    )
    return preset


async def update_preset(
    db: AsyncSession,
    preset_id: int,
    *,
    actor: str,
    name: str | None = None,
    description: str | None = None,
    config: PresetConfig | None = None,
) -> Preset:
    """Update fields; `config` replaces the stored config as a whole."""
    preset = await _require(db, preset_id)
    if name is not None and name != preset.name:
        if await crud.get_preset_by_name(db, name):
            raise PresetConflict(f"A preset named '{name}' already exists")
        preset.name = name
    if description is not None:
        preset.description = description
    if config is not None:
        preset.config = _serialize(config)
    await _commit_or_conflict(db, preset.name)
    await db.refresh(preset)
    fields = {"name": name, "description": description, "config": config}
    await crud.log_activity(
        db,
        "preset.updated",
        f"{actor} updated preset '{preset.name}'",
        {"id": preset.id, "fields": sorted(key for key, value in fields.items() if value is not None)},
        username=actor,
    )
    return preset


async def delete_preset(db: AsyncSession, preset_id: int, *, actor: str) -> None:
    """Delete a preset (images that used it keep `preset_id = NULL`)."""
    preset = await _require(db, preset_id)
    if preset.is_default:
        raise PresetConflict("The default preset cannot be deleted; make another preset the default first")
    name = preset.name
    await db.delete(preset)
    await db.commit()
    await crud.log_activity(db, "preset.deleted", f"{actor} deleted preset '{name}'", {"id": preset_id}, username=actor)


async def set_default(db: AsyncSession, preset_id: int, *, actor: str | None = None) -> Preset:
    """Make a preset the default. Logged when `actor` is given (a settings change writes its own entry)."""
    preset = await _require(db, preset_id)
    if not preset.is_default:
        await crud.set_default_preset(db, preset_id)
        invalidate_settings_cache()
        await db.refresh(preset)
    if actor is not None:
        await crud.log_activity(
            db,
            "preset.default",
            f"{actor} made '{preset.name}' the default preset",
            {"id": preset.id},
            username=actor,
        )
    return preset
