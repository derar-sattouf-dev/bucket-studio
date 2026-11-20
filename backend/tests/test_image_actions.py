"""Abort, retry-failed and notes endpoints, restore without a backup, and source-key validation."""

import threading
import time

import pytest

from app.core import image_pipeline, image_worker
from app.core.derivatives import DerivativeSpec, PublishConfig
from app.core.image_worker import TaskStatus
from app.core.source_filters import SourceFilters
from app.services import image_service, settings_service
from tests.conftest import login, make_image, wait_for

NO_MODELS = {"background": {"remove": False}, "upscale": {"enabled": False}}


@pytest.fixture
def preset_id(client, admin_headers) -> int:
    existing = {p["name"]: p["id"] for p in client.get("/presets/", headers=admin_headers).json()}
    if "Actions keep" in existing:
        return existing["Actions keep"]
    body = {"name": "Actions keep", "config": {**NO_MODELS, "output": {"format": "keep"}}}
    response = client.post("/presets/", headers=admin_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _sync(client, headers, fake_s3, keys: list[str], body: bytes | None = None) -> None:
    for key in keys:
        fake_s3.objects[key] = {"Body": body or make_image(fmt="JPEG"), "ContentType": "image/jpeg"}
    assert client.post("/images/sync", headers=headers).status_code == 200


def _image(client, headers, key: str) -> dict:
    body = client.get("/images/", headers=headers, params={"search": key, "page_size": 100}).json()
    return next(i for g in body["items"] for i in g["images"] if i["source_key"] == key)


def _process(client, headers, key: str, preset_id: int, expect: str = "processed") -> dict:
    response = client.post("/images/process", headers=headers, json={"keys": [key], "preset_id": preset_id})
    assert response.status_code == 200 and response.json()["queued"] == 1, response.text

    def finished():
        image = _image(client, headers, key)
        return image if image["status"] == expect and not image["is_processing"] else None

    return wait_for(finished, f"processing of {key} to end as {expect}")


def _wait_until_idle() -> None:
    wait_for(
        lambda: not any(t.status == TaskStatus.PROCESSING for t in list(image_worker._tasks.values())),
        "background processing to finish",
    )


# ── Abort ─────────────────────────────────────────────────────────────────────


def test_abort_stops_an_image_at_its_next_checkpoint(client, admin_headers, fake_s3, preset_id, monkeypatch):
    key = "images/actabort/a.jpg"
    _sync(client, admin_headers, fake_s3, [key])

    entered, release = threading.Event(), threading.Event()
    real = image_pipeline.run_pipeline

    def held(key_, plan, token):
        entered.set()
        deadline = time.monotonic() + 15
        while not release.is_set() and time.monotonic() < deadline:
            token.check()
            time.sleep(0.01)
        return real(key_, plan, token)

    monkeypatch.setattr(image_pipeline, "run_pipeline", held)
    try:
        queued = client.post("/images/process", headers=admin_headers, json={"keys": [key], "preset_id": preset_id})
        assert queued.json()["queued"] == 1
        assert entered.wait(timeout=15)
        assert _image(client, admin_headers, key)["is_processing"] is True

        # Already claimed: a second request does not start it twice.
        again = client.post("/images/process", headers=admin_headers, json={"keys": [key], "preset_id": preset_id})
        assert (again.json()["queued"], again.json()["already_processing"]) == (0, [key])

        aborted = client.post("/images/abort", headers=admin_headers, json={"key": key})
        assert (aborted.status_code, aborted.json()) == (200, {"aborted": key})

        def stopped():
            image = _image(client, admin_headers, key)
            return image if not image["is_processing"] and image["status"] == "failed" else None

        image = wait_for(stopped, "the abort to take effect")
    finally:
        release.set()

    assert image["error_message"] == "Aborted by user"
    assert image["retry_count"] == 0  # an abort is not a failed attempt
    assert "processed/images/actabort/a.jpg" not in fake_s3.objects
    assert image_worker.get_statuses([key]) == {key: TaskStatus.ABORTED}

    # Aborted images are not "failed" for the failed list or the bulk retry.
    failed = client.get("/images/failed", headers=admin_headers, params={"search": key}).json()
    assert failed["total"] == 0
    log = client.get("/activity/", headers=admin_headers, params={"search": key}).json()
    assert "image.abort" in {entry["event_type"] for entry in log}


def test_abort_is_refused_when_nothing_is_running(client, admin_headers, fake_s3):
    key = "images/actabort/idle.jpg"
    _sync(client, admin_headers, fake_s3, [key])

    idle = client.post("/images/abort", headers=admin_headers, json={"key": key})
    assert (idle.status_code, idle.json()["detail"]) == (409, "Image is not currently being processed")
    for bad in ("processed/images/actabort/idle.jpg", "images/../x.jpg", "elsewhere/a.jpg"):
        assert client.post("/images/abort", headers=admin_headers, json={"key": bad}).status_code == 400
    assert client.post("/images/abort", headers=admin_headers, json={"key": ""}).status_code == 422
    assert client.post("/images/abort", json={"key": key}).status_code == 401


# ── Retry failed ──────────────────────────────────────────────────────────────


def test_retry_failed_says_why_images_were_left_alone(client, admin_headers, fake_s3, preset_id):
    prefix = "images/actretry/"
    busy, retried = f"{prefix}busy.jpg", f"{prefix}retried.jpg"
    _sync(client, admin_headers, fake_s3, [busy, retried], body=b"this is not an image")
    for key in (busy, retried):
        _process(client, admin_headers, key, preset_id, expect="failed")
    _wait_until_idle()

    def retry(**params) -> dict:
        response = client.post("/images/retry-failed", headers=admin_headers, params=params)
        assert response.status_code == 200, response.text
        return response.json()

    total_failed = client.get("/images/failed", headers=admin_headers).json()["total"]
    assert total_failed >= 2

    # A retry limit of 0: every failed image is at the limit, none is "busy".
    at_limit = retry(max_retries=0)
    assert at_limit == {"queued": 0, "skipped_max_retries": total_failed, "skipped_other": 0}

    # Below the limit but claimed by other work: reported separately, not as "reached the retry limit".
    claimed = image_worker.register_task(busy)
    assert claimed is not None
    try:
        result = retry(preset_id=preset_id, max_retries=1000)
        assert result["skipped_max_retries"] == 0
        assert result["skipped_other"] >= 1
        assert result["queued"] >= 1
        assert result["queued"] + result["skipped_other"] == total_failed

        def retried_once_more():
            image = _image(client, admin_headers, retried)
            return image["retry_count"] == 2 and not image["is_processing"]

        wait_for(retried_once_more, "the retry of the failed image")
    finally:
        image_worker.finish_task(busy, TaskStatus.FAILED, "test")
    _wait_until_idle()
    assert _image(client, admin_headers, busy)["retry_count"] == 1  # it was skipped, not retried

    assert client.post("/images/retry-failed", headers=admin_headers, params={"max_retries": -1}).status_code == 422
    assert client.post("/images/retry-failed", headers=admin_headers, params={"preset_id": 999_999}).status_code == 404


def test_retry_failed_with_overwrite_is_admin_only(client, admin_headers):
    body = {"username": "retry_operator", "password": "operator-password-1", "admin_password": "step-up-password"}
    client.post("/users/", headers=admin_headers, json=body)
    operator = login(client, "retry_operator", "operator-password-1")
    assert client.post("/images/retry-failed", headers=operator, params={"replace": True}).status_code == 403


# ── Notes ─────────────────────────────────────────────────────────────────────


def test_notes_and_tags_are_saved_and_validated(client, admin_headers, fake_s3):
    key = "images/actnotes/a.jpg"
    _sync(client, admin_headers, fake_s3, [key])

    def patch(**body):
        return client.patch("/images/notes", headers=admin_headers, json=body)

    saved = patch(source_key=key, notes="Retake: glare on the left", tags="retake,glare")
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"source_key": key, "notes": "Retake: glare on the left", "tags": "retake,glare"}
    image = _image(client, admin_headers, key)
    assert (image["notes"], image["tags"]) == ("Retake: glare on the left", "retake,glare")
    assert image["status"] == "pending"  # annotations do not touch the processing state

    cleared = patch(source_key=key)
    assert cleared.json() == {"source_key": key, "notes": None, "tags": None}

    assert patch(source_key="images/actnotes/unknown.jpg", notes="x").status_code == 404
    assert patch(source_key="backup/images/actnotes/a.jpg", notes="x").status_code == 400
    assert patch(source_key=key, notes="x" * 5001).status_code == 422
    assert patch(source_key=key, tags="x" * 513).status_code == 422
    assert patch(notes="no key").status_code == 422
    assert client.patch("/images/notes", json={"source_key": key, "notes": "x"}).status_code == 401

    log = client.get("/activity/", headers=admin_headers, params={"search": key}).json()
    assert "image.notes" in {entry["event_type"] for entry in log}


# ── Restore without a backup ──────────────────────────────────────────────────


def test_restore_fails_cleanly_when_the_backup_object_is_missing(client, admin_headers, fake_s3, preset_id):
    key = "images/actrestore/a.jpg"
    backup = f"backup/{key}"
    original = make_image((600, 300), fmt="JPEG")
    _sync(client, admin_headers, fake_s3, [key], body=original)
    _process(client, admin_headers, key, preset_id)
    (published,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert published["status"] == "published", published
    published_bytes = fake_s3.body(key)
    assert published_bytes != original

    lost = fake_s3.objects.pop(backup)  # the backup object is gone from the bucket
    (result,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert result == {"key": key, "status": "error", "error": "Storage error (404)"}

    # Nothing was changed: the image is still published (not pending) and the bucket is as it was.
    image = _image(client, admin_headers, key)
    assert (image["status"], image["is_published"]) == ("processed", True)
    assert fake_s3.body(key) == published_bytes
    assert client.post("/images/reset-pending", headers=admin_headers, json={"keys": [key]}).json() == {"reset": 0}
    (again,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert again["status"] == "error" and "already published" in again["error"]

    # Once the backup is back, the same restore works.
    fake_s3.objects[backup] = lost
    (restored,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert restored == {"key": key, "status": "restored", "from": backup}
    assert fake_s3.body(key) == original
    image = _image(client, admin_headers, key)
    assert (image["status"], image["is_published"]) == ("pending", False)


# ── Source-key validation (unit) ──────────────────────────────────────────────


@pytest.fixture
def runtime() -> settings_service.SettingsOut:
    """Env defaults (images/, processed/, backup/) with a thumbnail derivative and one exclude glob."""
    defaults = settings_service._merge({}, None)
    return defaults.model_copy(
        update={
            "publish": PublishConfig(derivatives=[DerivativeSpec(name="{stem}_thumb.{ext}", width=300)]),
            "source_filters": SourceFilters(exclude_globs=["draft-*"]),
        }
    )


@pytest.mark.parametrize(
    "key",
    [
        "images/a.jpg",
        "images/shoes/red/side view.PNG",
        "images/a/b/c/d/e.webp",
        "images/a.b.jpeg",
        "images/thumb.jpg",  # not the derivative pattern
        "images/ünïcode/ß.jpg",
        "images/processed/a.jpg",  # a folder that merely shares a name with the output prefix
    ],
)
def test_source_keys_are_accepted(runtime, key):
    assert image_service.is_valid_source_key(key, runtime) is True


@pytest.mark.parametrize(
    "key",
    [
        # outside the source prefix
        "",
        "a.jpg",
        "other/a.jpg",
        "imagesX/a.jpg",
        "Images/a.jpg",
        "/images/a.jpg",
        " images/a.jpg",
        # the output and backup prefixes are never sources
        "processed/images/a.jpg",
        "backup/images/a.jpg",
        # prefix escape
        "images/../backup/images/a.jpg",
        "images/../a.jpg",
        "images/a/../../b.jpg",
        "images/./a.jpg",
        "images/..",
        "images/a/..",
        # empty segments
        "images//a.jpg",
        "images/a//b.jpg",
        "images/",
        "images/a/",
        # control characters and backslashes
        "images/a\\b.jpg",
        "images\\a.jpg",
        "images/a\x00.jpg",
        "images/a\n.jpg",
        "images/a\t.jpg",
        "images/\x1fa.jpg",
        # not an allowed image type
        "images/a.gif",
        "images/a.svg",
        "images/a",
        "images/a.jpg.exe",
        # derivative-looking names and excluded globs
        "images/a_thumb.jpg",
        "images/shoes/A_THUMB.JPG",
        "images/draft-1.jpg",
    ],
)
def test_keys_that_are_not_sources_are_rejected(runtime, key):
    assert image_service.is_valid_source_key(key, runtime) is False


def test_key_validation_follows_the_configured_prefixes(runtime):
    moved = runtime.model_copy(update={"source_prefix": "catalog/in/", "output_prefix": "catalog/out/"})
    assert image_service.is_valid_source_key("catalog/in/a.jpg", moved) is True
    assert image_service.is_valid_source_key("images/a.jpg", moved) is False
    assert image_service.is_valid_source_key("catalog/out/a.jpg", moved) is False

    with pytest.raises(image_service.InvalidImageKeys, match="2 key"):
        image_service.validate_source_keys(["images/a.jpg", "images/../a.jpg", "backup/a.jpg"], runtime)
    image_service.validate_source_keys(["images/a.jpg", "images/b/c.png"], runtime)
