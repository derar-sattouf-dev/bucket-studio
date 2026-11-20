"""Large buckets: paginated review / failed lists, capped groups, background bulk publish,
the presign cache and the pipeline's own thread pool. All on an in-memory bucket."""

import asyncio
import threading
import time

import pytest

from app.core import image_pipeline, s3
from app.services import image_service
from tests.conftest import make_image

NO_MODELS = {"background": {"remove": False}, "upscale": {"enabled": False}}


@pytest.fixture
def preset_id(client, admin_headers) -> int:
    existing = {p["name"]: p["id"] for p in client.get("/presets/", headers=admin_headers).json()}
    if "Scale keep" in existing:
        return existing["Scale keep"]
    body = {"name": "Scale keep", "config": {**NO_MODELS, "output": {"format": "keep"}}}
    response = client.post("/presets/", headers=admin_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _wait_for(condition, what: str, timeout: float = 20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(f"{what} did not happen in time")


def _sync(client, headers, fake_s3, keys: list[str], body: bytes | None = None) -> None:
    for key in keys:
        fake_s3.objects[key] = {"Body": body or make_image(fmt="JPEG"), "ContentType": "image/jpeg"}
    assert client.post("/images/sync", headers=headers).status_code == 200


def _group_list(client, headers, search: str, **params) -> dict:
    response = client.get("/images/", headers=headers, params={"search": search, "page_size": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _images(client, headers, search: str) -> dict[str, dict]:
    return {i["source_key"]: i for g in _group_list(client, headers, search)["items"] for i in g["images"]}


def _process(client, headers, keys: list[str], preset: int, expect: str = "processed") -> None:
    response = client.post("/images/process", headers=headers, json={"keys": keys, "preset_id": preset})
    assert response.status_code == 200, response.text
    assert response.json()["queued"] == len(keys)

    def finished():
        images = _images(client, headers, keys[0].rsplit("/", 1)[0] + "/")
        return all(images[k]["status"] == expect and not images[k]["is_processing"] for k in keys)

    _wait_for(finished, f"processing to end as {expect}")


def _wait_for_bulk_publish(client, headers) -> dict:
    def finished():
        status = client.get("/images/publish-all/status", headers=headers).json()
        return None if status["running"] else status

    return _wait_for(finished, "the bulk publish to finish")


# ── Review / failed lists ─────────────────────────────────────────────────────


def test_review_list_is_paginated_and_searchable(client, admin_headers, fake_s3, preset_id):
    prefix = "images/scalerev/"
    keys = [f"{prefix}{n}.jpg" for n in "abc"]
    _sync(client, admin_headers, fake_s3, keys)
    _process(client, admin_headers, keys, preset_id)

    def review(**params):
        return client.get("/images/review", headers=admin_headers, params=params)

    first = review(search=prefix, page_size=2).json()
    assert (first["total"], first["page"], first["page_size"], first["total_pages"]) == (3, 1, 2, 2)
    assert len(first["items"]) == 2 and all(i["processed_url"] for i in first["items"])
    second = review(search=prefix, page_size=2, page=2).json()
    assert len(second["items"]) == 1
    assert {i["source_key"] for i in first["items"] + second["items"]} == set(keys)

    assert [i["source_key"] for i in review(search=f"{prefix}b").json()["items"]] == [f"{prefix}b.jpg"]
    assert review(search="no-such-image-anywhere").json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 30,
        "total_pages": 1,
    }
    assert review().json()["total"] >= 3  # no search: everything waiting for review

    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 101}, {"search": "x" * 201}):
        assert review(**bad).status_code == 422, bad


def test_failed_list_is_paginated_and_retry_still_covers_every_failure(client, admin_headers, fake_s3, preset_id):
    prefix = "images/scalefail/"
    keys = [f"{prefix}{n}.jpg" for n in "abc"]
    _sync(client, admin_headers, fake_s3, keys, body=b"this is not an image")
    _process(client, admin_headers, keys, preset_id, expect="failed")

    def failed(**params):
        return client.get("/images/failed", headers=admin_headers, params=params)

    first = failed(search=prefix, page_size=2).json()
    assert (first["total"], first["total_pages"], len(first["items"])) == (3, 2, 2)
    assert len(failed(search=prefix, page_size=2, page=2).json()["items"]) == 1
    assert all(i["status"] == "failed" and i["retry_count"] == 1 for i in first["items"])

    error = first["items"][0]["error_message"]
    assert error and failed(search=error).json()["total"] >= 3  # the search also matches the error text
    assert failed(search=f"{prefix}c").json()["total"] == 1
    for bad in ({"page": 0}, {"page_size": 101}, {"search": "x" * 201}):
        assert failed(**bad).status_code == 422, bad

    skipped = client.post("/images/retry-failed", headers=admin_headers, params={"max_retries": 0}).json()
    assert skipped["queued"] == 0 and skipped["skipped_max_retries"] >= 3

    retried = client.post("/images/retry-failed", headers=admin_headers, params={"preset_id": preset_id}).json()
    assert retried["queued"] >= 3

    def retried_again():
        items = failed(search=prefix).json()["items"]
        return len(items) == 3 and all(i["retry_count"] == 2 and not i["is_processing"] for i in items)

    _wait_for(retried_again, "the retry of the failed images")


# ── Groups ────────────────────────────────────────────────────────────────────


def test_groups_are_capped_and_the_rest_is_paged(client, admin_headers, fake_s3, preset_id, monkeypatch):
    monkeypatch.setattr(image_service, "GROUP_IMAGE_LIMIT", 2)
    prefix = "images/scalegrp/"
    keys = [f"{prefix}{n}.jpg" for n in range(5)]
    _sync(client, admin_headers, fake_s3, [*keys, "images/scaleflat.jpg"])

    page = _group_list(client, admin_headers, prefix, sort_by="id", sort_order="asc")
    (group,) = page["items"]
    assert page["grouped"] is True
    assert (group["group"], group["image_count"], group["publishable_count"]) == ("scalegrp", 5, 0)
    assert [i["source_key"] for i in group["images"]] == keys[:2]

    def more(**params):
        query = {"group": "scalegrp", "search": prefix, "sort_by": "id", "sort_order": "asc", **params}
        return client.get("/images/group", headers=admin_headers, params=query)

    rest = more(offset=2, limit=2).json()
    assert (rest["group"], rest["total"], rest["offset"], rest["limit"]) == ("scalegrp", 5, 2, 2)
    assert [i["source_key"] for i in rest["items"]] == keys[2:4]
    assert [i["source_key"] for i in more(offset=4).json()["items"]] == keys[4:]
    assert more(offset=5).json()["items"] == []
    for bad in ({"offset": -1}, {"limit": 0}, {"limit": 101}, {"group": "x" * 1025}):
        assert more(**bad).status_code == 422, bad

    # Without `group`: the images that have no group.
    ungrouped = client.get("/images/group", headers=admin_headers, params={"search": "images/scaleflat"}).json()
    assert ungrouped["group"] is None
    assert [i["source_key"] for i in ungrouped["items"]] == ["images/scaleflat.jpg"]

    # Group actions cover the whole group, not just the two images that were listed.
    body = {"group": "scalegrp", "preset_id": preset_id}
    queued = client.post("/images/process-group", headers=admin_headers, json=body)
    assert queued.status_code == 200, queued.text
    assert (queued.json()["queued"], queued.json()["skipped_busy"]) == (5, 0)

    def all_processed():
        items = more(limit=100).json()["items"]
        return all(i["status"] == "processed" and not i["is_processing"] for i in items)

    _wait_for(all_processed, "processing of the group")
    (group,) = _group_list(client, admin_headers, prefix)["items"]
    assert (group["image_count"], group["publishable_count"], len(group["images"])) == (5, 5, 2)

    started = client.post("/images/publish-group", headers=admin_headers, json={"group": "scalegrp"})
    assert (started.status_code, started.json()) == (202, {"total": 5})
    status = _wait_for_bulk_publish(client, admin_headers)
    assert (status["total"], status["done"], status["published"], status["failed"]) == (5, 5, 5, 0)
    assert all(i["is_published"] for i in more(limit=100).json()["items"])

    missing = client.post("/images/process-group", headers=admin_headers, json={"group": "no-such-group"})
    assert missing.status_code == 404


# ── Publish all ───────────────────────────────────────────────────────────────


def test_publish_all_runs_in_the_background_one_at_a_time(client, admin_headers, fake_s3, preset_id, monkeypatch):
    prefix = "images/scalepub/"
    keys = [f"{prefix}{n}.jpg" for n in "abc"]
    _sync(client, admin_headers, fake_s3, keys)
    _process(client, admin_headers, keys, preset_id)

    release = threading.Event()
    real_get = fake_s3.get_object

    def slow_get(**kwargs):
        release.wait(timeout=15)
        return real_get(**kwargs)

    monkeypatch.setattr(fake_s3, "get_object", slow_get)
    try:
        started = client.post("/images/publish-all", headers=admin_headers)
        assert started.status_code == 202, started.text
        total = started.json()["total"]
        assert total >= 3

        status = client.get("/images/publish-all/status", headers=admin_headers).json()
        assert status["running"] is True and status["total"] == total and status["done"] == 0
        assert status["started_at"] and status["finished_at"] is None

        assert client.post("/images/publish-all", headers=admin_headers).status_code == 409
        again = client.post("/images/publish-group", headers=admin_headers, json={"group": "scalepub"})
        assert again.status_code == 409
    finally:
        release.set()

    status = _wait_for_bulk_publish(client, admin_headers)
    assert status["done"] == total and status["published"] + status["failed"] == total
    assert status["published"] >= 3 and status["finished_at"]
    assert len(status["errors"]) == min(status["failed"], 100)
    images = _images(client, admin_headers, prefix)
    assert all(images[k]["is_published"] for k in keys)
    assert all(fake_s3.body(f"backup/{k}") for k in keys)

    # One summary entry for the run, none per image.
    log = client.get("/activity/", headers=admin_headers, params={"search": prefix, "limit": 200}).json()
    assert not [entry for entry in log if entry["event_type"] == "publish"]
    summaries = client.get("/activity/", headers=admin_headers, params={"search": "image.publish_all"}).json()
    assert f"published {status['published']}/{total}" in summaries[0]["message"]

    # A finished run does not block the next one; a run with nothing to publish ends at once.
    empty = client.post("/images/publish-group", headers=admin_headers, json={"group": "no-such-group"})
    assert (empty.status_code, empty.json()) == (202, {"total": 0})
    status = client.get("/images/publish-all/status", headers=admin_headers).json()
    assert (status["running"], status["total"], status["done"]) == (False, 0, 0)


# ── Presign cache / thread pool ───────────────────────────────────────────────


def test_presign_cache_evicts_the_least_recently_used_entry(fake_s3, monkeypatch):
    monkeypatch.setattr(s3, "_PRESIGN_CACHE_MAX", 3)
    for name in "abc":
        s3.presign_get(f"images/{name}.jpg", 3600)
    s3.presign_get("images/a.jpg", 3600)  # a hit makes `a` the most recently used
    s3.presign_get("images/d.jpg", 3600)

    assert [key for key, _ in s3._presign_cache] == ["images/c.jpg", "images/a.jpg", "images/d.jpg"]

    calls: list[str] = []
    real_sign = fake_s3.generate_presigned_url

    def counting_sign(operation, Params, ExpiresIn):
        calls.append(Params["Key"])
        return real_sign(operation, Params, ExpiresIn)

    monkeypatch.setattr(fake_s3, "generate_presigned_url", counting_sign)
    s3.presign_get("images/a.jpg", 3600)
    s3.presign_get("images/b.jpg", 3600)
    assert calls == ["images/b.jpg"]  # `a` survived, only the evicted `b` is signed again


def test_presign_cache_does_not_reuse_expired_urls(fake_s3, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(s3.time, "monotonic", lambda: now[0])
    first = s3.presign_get("images/a.jpg", 3600)
    assert s3.presign_get("images/a.jpg", 3600) is first
    now[0] += 3600
    assert s3.presign_get("images/a.jpg", 3600) is not first
    assert len(s3._presign_cache) == 1


def test_the_pipeline_runs_on_its_own_thread_pool(monkeypatch):
    from app.config import MAX_PROCESS_CONCURRENCY
    from app.services.settings_service import SettingsPatch

    monkeypatch.setattr(image_pipeline, "run_pipeline", lambda *_args: threading.current_thread().name)
    thread = asyncio.run(image_pipeline._run_with_retries("images/a.jpg", None, None))
    assert thread.startswith("pipeline")

    # The pool has a thread for every image the settings allow to be processed at once.
    assert image_pipeline._PIPELINE_EXECUTOR._max_workers == MAX_PROCESS_CONCURRENCY
    assert SettingsPatch(process_concurrency=MAX_PROCESS_CONCURRENCY).process_concurrency == MAX_PROCESS_CONCURRENCY
    with pytest.raises(ValueError):
        SettingsPatch(process_concurrency=MAX_PROCESS_CONCURRENCY + 1)
