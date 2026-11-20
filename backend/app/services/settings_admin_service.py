"""Use cases behind the Settings API that change state: patching settings and resetting the database.

Kept beside `settings_service` (the settings model and its storage) because these also touch
presets, the scheduler and the running background work, all of which depend on `settings_service`.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.job_registry import get_running_job
from app.db.crud import log_activity
from app.db.migrate import rebuild_schema
from app.db.session import AsyncSessionLocal
from app.scheduler import reschedule_sync
from app.services import preset_service, publish_service, sync_service
from app.services.settings_service import (
    AdminSettingsPatch,
    SettingsOut,
    SettingsPatch,
    apply_image_limits,
    get_runtime_settings,
    invalidate_settings_cache,
    update_settings,
    validate_admin_changes,
)

logger = logging.getLogger(__name__)


class NoChanges(Exception):
    """The patch contains no fields."""


class ResetRefused(Exception):
    """The database cannot be reset right now; the message is safe to show."""


async def change_runtime_settings(db: AsyncSession, patch: SettingsPatch, *, actor: str) -> SettingsOut:
    """Apply a runtime patch (`default_preset_id` switches the default preset). Raises `PresetNotFound`."""
    requested = patch.model_dump(exclude_none=True)
    updates = dict(requested)
    default_preset_id = updates.pop("default_preset_id", None)
    if default_preset_id is not None:
        await preset_service.set_default(db, default_preset_id)

    result = await update_settings(db, updates)
    changed = [*updates, *(["default_preset_id"] if default_preset_id is not None else [])]
    if changed:
        await log_activity(
            db, "settings.changed", f"{actor} updated settings: {', '.join(changed)}", requested, username=actor
        )
    if "sync_interval_minutes" in updates:
        reschedule_sync(result.sync_interval_minutes)
    return result


async def change_admin_settings(db: AsyncSession, patch: AdminSettingsPatch, *, actor: str) -> SettingsOut:
    """Apply a step-up patch (the admin password was checked by the caller).

    Raises `NoChanges`, or `InvalidSettings` when the result would be inconsistent.
    """
    updates = patch.model_dump(mode="json", exclude_none=True, exclude={"admin_password"})
    if not updates:
        raise NoChanges
    validate_admin_changes(await get_runtime_settings(db), updates)

    result = await update_settings(db, updates)
    await log_activity(
        db, "settings.admin_changed", f"{actor} changed admin settings: {', '.join(updates)}", updates, username=actor
    )
    return result


def _running_work() -> str | None:
    if get_running_job() is not None:
        return "a batch job"
    if sync_service.is_sync_running():
        return "a sync"
    if publish_service.bulk_publish_status().running:
        return "a bulk publish"
    return None


async def reset_database(*, actor: str) -> None:
    """Empty every application table, then re-seed presets and go back to the default settings.

    The schema is rebuilt through Alembic (down to base, up to head), so it is always the migrated
    one. Refused while background work that writes to the database is running.
    """
    busy = _running_work()
    if busy is not None:
        raise ResetRefused(f"Cannot reset the database while {busy} is running")

    await asyncio.to_thread(rebuild_schema)
    invalidate_settings_cache()
    async with AsyncSessionLocal() as db:
        await preset_service.seed_presets(db)
        apply_image_limits(await get_runtime_settings(db))
        await log_activity(db, "settings.reset_db", f"{actor} reset the database", username=actor)
    logger.warning("Database reset by %s", actor)
