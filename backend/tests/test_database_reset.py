"""`POST /settings/reset-db`: the schema is rebuilt through Alembic and running work blocks it."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from PIL import Image
from sqlalchemy import create_engine, inspect, text

from app.db import migrate
from app.db.models import Base
from app.db.session import SYNC_DATABASE_URL
from app.services import publish_service, sync_service
from tests.conftest import login, make_image

RESET = {"admin_password": "step-up-password", "confirm": "RESET"}


def _reset(client, headers):
    return client.post("/settings/reset-db", headers=headers, json=RESET)


def test_rebuild_schema_empties_the_database_and_leaves_the_migrated_schema(tmp_path):
    url = f"sqlite:///{tmp_path / 'rebuild.db'}"
    migrate.run_migrations(url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO images (source_key, status, retry_count, is_published) VALUES ('k', 'PENDING', 0, 0)")
            )
            conn.execute(text("INSERT INTO settings (key, value) VALUES ('group_depth', '3')"))

        migrate.rebuild_schema(url)

        with engine.connect() as conn:
            head = ScriptDirectory.from_config(migrate.alembic_config()).get_current_head()
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
            assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
            for table in ("images", "settings", "users", "presets", "activity_log", "batch_job_history"):
                assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 0, table  # noqa: S608
    finally:
        engine.dispose()


def test_reset_is_refused_while_a_sync_or_a_bulk_publish_is_running(client, admin_headers, monkeypatch):
    monkeypatch.setattr(sync_service, "is_sync_running", lambda: True)
    refused = _reset(client, admin_headers)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Cannot reset the database while a sync is running",
    )
    monkeypatch.undo()

    monkeypatch.setattr(publish_service, "_bulk", publish_service.BulkPublishState(running=True))
    refused = _reset(client, admin_headers)
    assert refused.status_code == 409 and "bulk publish" in refused.json()["detail"]
    monkeypatch.undo()

    # Refusals changed nothing (the running-batch-job case is covered in test_jobs.py).
    assert client.get("/presets/", headers=admin_headers).json()


def test_reset_wipes_the_data_reseeds_presets_and_restores_default_settings(client, admin_headers, fake_s3):
    created = client.post(
        "/users/",
        headers=admin_headers,
        json={"username": "reset_user", "password": "reset-password-1", "admin_password": "step-up-password"},
    )
    assert created.status_code == 201, created.text
    user_headers = login(client, "reset_user", "reset-password-1")
    fake_s3.objects["images/resetdb/a.jpg"] = {"Body": make_image(fmt="JPEG"), "ContentType": "image/jpeg"}
    assert client.post("/images/sync", headers=admin_headers).status_code == 200
    assert client.patch("/settings/", headers=admin_headers, json={"max_image_megapixels": 2}).status_code == 200
    assert Image.MAX_IMAGE_PIXELS == 2_000_000

    response = _reset(client, admin_headers)
    assert (response.status_code, response.json()["ok"]) == (200, True)

    # Data is gone, including the user (whose token is revoked with it)...
    assert client.get("/images/", headers=admin_headers).json()["total_images"] == 0
    assert client.get("/users/", headers=admin_headers).json() == []
    assert client.get("/auth/me", headers=user_headers).status_code == 401
    assert client.get("/activity/batch-history", headers=admin_headers).json() == []
    # ...settings are back to the env defaults, and the Pillow limit follows them...
    assert client.get("/settings/", headers=admin_headers).json()["max_image_megapixels"] == 80
    assert Image.MAX_IMAGE_PIXELS == 80_000_000
    # ...the built-in presets are seeded again with exactly one default...
    presets = client.get("/presets/", headers=admin_headers).json()
    assert presets and [p["is_default"] for p in presets].count(True) == 1
    # ...and the only thing in the activity log is the reset itself.
    log = client.get("/activity/", headers=admin_headers, params={"limit": 200}).json()
    assert [(e["event_type"], e["username"]) for e in log] == [("settings.reset_db", "admin")]

    # The schema is the migrated one, at the head revision.
    engine = create_engine(SYNC_DATABASE_URL)
    try:
        with engine.connect() as conn:
            head = ScriptDirectory.from_config(migrate.alembic_config()).get_current_head()
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
            assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
            assert "images" in inspect(conn).get_table_names()
    finally:
        engine.dispose()

    # The app keeps working on the rebuilt database.
    assert client.post("/images/sync", headers=admin_headers).json()["synced"] == 1
