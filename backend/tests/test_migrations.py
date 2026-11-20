"""The Alembic history builds exactly the schema the ORM models describe."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db import migrate
from app.db.models import Base


def _head() -> str:
    head = ScriptDirectory.from_config(migrate.alembic_config()).get_current_head()
    assert head is not None
    return head


def test_fresh_database_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    migrate.run_migrations(url)
    migrate.run_migrations(url)  # idempotent

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == _head()
            assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
            tables = set(inspect(conn).get_table_names())
    finally:
        engine.dispose()
    assert {"images", "presets", "settings", "users", "activity_log", "batch_job_history"} <= tables


def test_single_default_is_enforced_by_the_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'presets.db'}"
    migrate.run_migrations(url)
    engine = create_engine(url)
    insert = text("INSERT INTO presets (name, description, config, is_default) VALUES (:name, '', '{}', 1)")
    try:
        with engine.begin() as conn:
            conn.execute(insert, {"name": "a"})
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(insert, {"name": "b"})
    finally:
        engine.dispose()
