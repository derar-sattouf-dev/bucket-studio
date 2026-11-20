"""Sync → process with a preset → publish (backup + derivatives) → restore, on an in-memory bucket."""

import io
import time

import pytest
from PIL import Image

from tests.conftest import login, make_image

NO_MODELS = {
    "background": {"remove": False},
    "upscale": {"enabled": False},
    "canvas": {"enabled": True, "width": 400, "height": 400},
}

THUMBNAIL = {"derivatives": [{"name": "{stem}_thumb.{ext}", "width": 300, "height": 300}]}
STEP_UP = {"admin_password": "step-up-password"}


@pytest.fixture(autouse=True)
def _publish_writes_a_thumbnail(client, admin_headers):
    """These tests cover derivatives; none are configured by default."""
    response = client.patch("/settings/admin", headers=admin_headers, json={**STEP_UP, "publish": THUMBNAIL})
    assert response.status_code == 200, response.text
    yield
    client.patch("/settings/admin", headers=admin_headers, json={**STEP_UP, "publish": {}})


@pytest.fixture
def preset_ids(client, admin_headers) -> dict[str, int]:
    ids = {}
    for name, output in (("Flow keep", {"format": "keep"}), ("Flow png", {"format": "png"})):
        existing = {p["name"]: p["id"] for p in client.get("/presets/", headers=admin_headers).json()}
        if name in existing:
            ids[name] = existing[name]
            continue
        response = client.post(
            "/presets/", headers=admin_headers, json={"name": name, "config": {**NO_MODELS, "output": output}}
        )
        assert response.status_code == 201, response.text
        ids[name] = response.json()["id"]
    return ids


def _images(client, headers, search: str) -> dict[str, dict]:
    body = client.get("/images/", headers=headers, params={"search": search, "page_size": 100}).json()
    return {img["source_key"]: img for group in body["items"] for img in group["images"]}


def _process(client, headers, key: str, preset_id: int) -> dict:
    response = client.post("/images/process", headers=headers, json={"keys": [key], "preset_id": preset_id})
    assert response.status_code == 200, response.text
    assert response.json()["queued"] == 1
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        image = _images(client, headers, key)[key]
        if image["status"] in ("processed", "failed") and not image["is_processing"]:
            return image
        time.sleep(0.05)
    raise AssertionError("processing did not finish")


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_full_cycle(client, admin_headers, fake_s3, preset_ids):
    key = "images/flow/p1/a.jpg"
    original = make_image((600, 300), fmt="JPEG")
    fake_s3.objects[key] = {"Body": original, "ContentType": "image/jpeg"}
    fake_s3.objects["images/flow/p1/a_thumb.jpg"] = {"Body": make_image(fmt="JPEG"), "ContentType": "image/jpeg"}

    assert client.post("/images/sync", headers=admin_headers).status_code == 200
    listed = _images(client, admin_headers, "images/flow/p1/")
    assert set(listed) == {key}  # the derivative-looking file is not a source
    assert listed[key]["group_key"] == "flow"

    image = _process(client, admin_headers, key, preset_ids["Flow keep"])
    assert image["status"] == "processed", image["error_message"]
    assert image["processed_key"] == "processed/images/flow/p1/a.jpg"
    assert (image["processed_by"], image["preset_id"]) == ("local", preset_ids["Flow keep"])
    processed = fake_s3.body("processed/images/flow/p1/a.jpg")
    assert _size(processed) == (400, 400)
    review = client.get("/images/review", headers=admin_headers, params={"search": key}).json()
    assert [img["source_key"] for img in review["items"]] == [key]

    (result,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert result["status"] == "published", result
    assert fake_s3.body("backup/images/flow/p1/a.jpg") == original
    assert "ACL" not in fake_s3.objects["backup/images/flow/p1/a.jpg"]
    assert fake_s3.body(key) == processed  # copied as-is, no re-render
    assert "ACL" not in fake_s3.objects[key]  # no ACL by default (works with ACL-disabled buckets)
    assert _size(fake_s3.body("images/flow/p1/a_thumb.jpg")) == (300, 300)

    image = _images(client, admin_headers, key)[key]
    assert image["is_published"] is True
    assert set(image["derivative_urls"]) == {"a_thumb.jpg"}
    assert image["backup_url"].endswith("/backup/images/flow/p1/a.jpg?X-Amz-Expires=3600")

    (again,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert again["status"] == "error" and "already published" in again["error"]
    assert fake_s3.body("backup/images/flow/p1/a.jpg") == original  # backup untouched

    (restored,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert restored["status"] == "restored", restored
    assert fake_s3.body(key) == original
    assert _size(fake_s3.body("images/flow/p1/a_thumb.jpg")) == (300, 150)  # regenerated from the original
    image = _images(client, admin_headers, key)[key]
    assert (image["status"], image["is_published"], image["derivative_urls"]) == ("pending", False, {})


def test_publish_refuses_a_different_output_format(client, admin_headers, fake_s3, preset_ids):
    key = "images/flow/p2/b.jpg"
    fake_s3.objects[key] = {"Body": make_image(fmt="JPEG"), "ContentType": "image/jpeg"}
    client.post("/images/sync", headers=admin_headers)

    image = _process(client, admin_headers, key, preset_ids["Flow png"])
    assert image["processed_key"] == "processed/images/flow/p2/b.png"

    (result,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert result["status"] == "error" and "format" in result["error"]
    assert "backup/images/flow/p2/b.jpg" not in fake_s3.objects

    (reset,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert reset["status"] == "reset"
    assert "processed/images/flow/p2/b.png" not in fake_s3.objects


def test_key_and_permission_checks(client, admin_headers, fake_s3):
    fake_s3.objects["images/flow/p3/c.jpg"] = {"Body": make_image(fmt="JPEG"), "ContentType": "image/jpeg"}
    client.post("/images/sync", headers=admin_headers)

    for bad in ("processed/images/flow/p3/c.jpg", "images/flow/p3/c_thumb.jpg", "images/../etc/c.jpg"):
        assert client.post("/images/publish", headers=admin_headers, json={"keys": [bad]}).status_code == 400
    assert (
        client.post("/images/publish", headers=admin_headers, json={"keys": ["images/flow/none.jpg"]}).status_code
        == 404
    )
    assert (
        client.post(
            "/images/process", headers=admin_headers, json={"keys": ["images/flow/p3/c.jpg"], "preset_id": 999999}
        )
    ).status_code == 404
    assert (
        client.post(
            "/images/process", headers=admin_headers, json={"keys": ["images/flow/p3/c.jpg"], "engine": "openai"}
        )
    ).status_code == 422

    client.post(
        "/users/",
        headers=admin_headers,
        json={"username": "flow_operator", "password": "operator-password-1", "admin_password": "step-up-password"},
    )
    operator = login(client, "flow_operator", "operator-password-1")
    body = {"keys": ["images/flow/p3/c.jpg"], "replace": True}
    assert client.post("/images/process", headers=operator, json=body).status_code == 403
    assert client.post("/jobs/start", headers=operator, json={"overwrite_original": True}).status_code == 403


def test_group_depth_changes_regroup_images(client, admin_headers, fake_s3):
    for key in ("images/grp/x/1.png", "images/grp/y/2.png", "images/top.png"):
        fake_s3.objects[key] = {"Body": make_image(), "ContentType": "image/png"}
    client.post("/images/sync", headers=admin_headers)

    def groups(**params) -> dict:
        query = {"search": "images/", "page_size": 100, **params}
        return client.get("/images/", headers=admin_headers, params=query).json()

    by_group = {g["group"]: [i["source_key"] for i in g["images"]] for g in groups()["items"]}
    assert "images/top.png" in by_group[None]
    assert set(by_group["grp"]) == {"images/grp/x/1.png", "images/grp/y/2.png"}

    assert client.patch("/settings/", headers=admin_headers, json={"group_depth": 2}).status_code == 200
    by_group = {g["group"]: [i["source_key"] for i in g["images"]] for g in groups()["items"]}
    assert by_group["grp/x"] == ["images/grp/x/1.png"]
    assert by_group["grp/y"] == ["images/grp/y/2.png"]

    assert client.patch("/settings/", headers=admin_headers, json={"group_depth": 0}).status_code == 200
    page = groups(page_size=2)
    assert len(page["items"]) == 1 and page["items"][0]["group"] is None
    assert len(page["items"][0]["images"]) == 2
    assert page["total_pages"] == -(-page["total_images"] // 2)

    assert client.patch("/settings/", headers=admin_headers, json={"group_depth": 1}).status_code == 200
    by_group = {g["group"]: g["images"] for g in groups()["items"]}
    assert {i["group_key"] for i in by_group["grp"]} == {"grp"}


def _processed_image(client, headers, fake_s3, preset_ids, key: str) -> bytes:
    """Sync and process `key`; returns the original bytes."""
    original = make_image((600, 300), fmt="JPEG")
    fake_s3.objects[key] = {"Body": original, "ContentType": "image/jpeg"}
    assert client.post("/images/sync", headers=headers).status_code == 200
    assert _process(client, headers, key, preset_ids["Flow keep"])["status"] == "processed"
    return original


def test_retrying_a_half_finished_publish_keeps_the_original(client, admin_headers, fake_s3, preset_ids, monkeypatch):
    """A publish that fails after overwriting the source must not back up the processed image on retry."""
    key = "images/flow/p5/e.jpg"
    backup = "backup/images/flow/p5/e.jpg"
    original = _processed_image(client, admin_headers, fake_s3, preset_ids, key)
    processed = fake_s3.body("processed/images/flow/p5/e.jpg")

    real_put = fake_s3.put_object

    def failing_put(*, Key: str, **kwargs):
        if Key.endswith("_thumb.jpg"):
            raise RuntimeError("storage unavailable")
        real_put(Key=Key, **kwargs)

    monkeypatch.setattr(fake_s3, "put_object", failing_put)
    (failed,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert failed["status"] == "error"
    assert fake_s3.body(key) == processed  # the source was already overwritten...
    assert fake_s3.body(backup) == original  # ...and the backup holds the original
    assert _images(client, admin_headers, key)[key]["is_published"] is False

    # A DB-only reset would forget the backup while the source holds the processed image.
    assert client.post("/images/reset-pending", headers=admin_headers, json={"keys": [key]}).json() == {"reset": 0}

    monkeypatch.setattr(fake_s3, "put_object", real_put)
    (retried,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert retried["status"] == "published", retried
    assert fake_s3.body(backup) == original  # not replaced by the processed image

    (restored,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert restored["status"] == "restored"
    assert fake_s3.body(key) == original


def test_restore_after_a_half_finished_publish_brings_the_original_back(
    client, admin_headers, fake_s3, preset_ids, monkeypatch
):
    key = "images/flow/p6/f.jpg"
    original = _processed_image(client, admin_headers, fake_s3, preset_ids, key)

    real_put = fake_s3.put_object

    def failing_put(*, Key: str, **kwargs):
        if Key.endswith("_thumb.jpg"):
            raise RuntimeError("storage unavailable")
        real_put(Key=Key, **kwargs)

    monkeypatch.setattr(fake_s3, "put_object", failing_put)
    client.post("/images/publish", headers=admin_headers, json={"keys": [key]})
    monkeypatch.setattr(fake_s3, "put_object", real_put)
    assert fake_s3.body(key) != original

    (restored,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert restored["status"] == "restored", restored
    assert fake_s3.body(key) == original
    assert _images(client, admin_headers, key)[key]["status"] == "pending"


def test_an_image_is_published_by_one_request_at_a_time(client, admin_headers, fake_s3, preset_ids):
    from app.services import publish_service

    key = "images/flow/p7/g.jpg"
    original = _processed_image(client, admin_headers, fake_s3, preset_ids, key)

    with publish_service._claim(key) as claimed:  # another request is publishing this image
        assert claimed
        (busy,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
        assert busy["status"] == "error" and "already being published" in busy["error"]
        (busy,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
        assert busy["status"] == "error"
    assert fake_s3.body(key) == original
    assert "backup/images/flow/p7/g.jpg" not in fake_s3.objects

    (result,) = client.post("/images/publish", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert result["status"] == "published"


def test_restore_uses_the_backup_recorded_at_publish_time(client, admin_headers, fake_s3, preset_ids):
    """Changing the backup prefix after publishing must not strand the backup."""
    from app.services import settings_service

    key = "images/flow/p8/h.jpg"
    original = _processed_image(client, admin_headers, fake_s3, preset_ids, key)
    client.post("/images/publish", headers=admin_headers, json={"keys": [key]})

    real = settings_service.get_runtime_settings

    async def moved_backup_prefix(db):
        return (await real(db)).model_copy(update={"backup_prefix": "elsewhere/"})

    import app.services.image_service as image_service
    import app.services.publish_service as publish_service

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(image_service, "get_runtime_settings", moved_backup_prefix)
        mp.setattr(publish_service, "get_runtime_settings", moved_backup_prefix)
        (restored,) = client.post("/images/restore", headers=admin_headers, json={"keys": [key]}).json()["results"]
    assert restored == {"key": key, "status": "restored", "from": "backup/images/flow/p8/h.jpg"}
    assert fake_s3.body(key) == original
