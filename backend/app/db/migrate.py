"""Programmatic Alembic runner: brings the database to the latest revision on startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.session import SYNC_DATABASE_URL

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(url: str = SYNC_DATABASE_URL) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(url: str = SYNC_DATABASE_URL) -> None:
    command.upgrade(alembic_config(url), "head")


def rebuild_schema(url: str = SYNC_DATABASE_URL) -> None:
    """Empty the database by walking the migrations down and up again.

    The result is by construction the migrated schema (same tables, indexes and `alembic_version`
    as a fresh install), which `Base.metadata.create_all` would not guarantee.
    """
    cfg = alembic_config(url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
