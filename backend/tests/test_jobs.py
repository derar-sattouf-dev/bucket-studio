"""Batch jobs end to end on the in-memory bucket: run, history, stop, skip and the one-job rule."""

import threading
import time

import pytest

from app.core import image_pipeline
from tests.conftest import make_image, wait_for

NO_MODELS = {"background": {"remove": False}, "upscale": {"enabled": False}}
STEP_UP = {"admin_password": "step-up-password"}


@pytest.fixture
def preset_id(client, admin_headers) -> int:
    existing = {p["name"]: p["id"] for p in client.get("/presets/", headers=admin_headers).json()}
    if "Jobs keep" in existing:
        return existing["Jobs keep"]
    body = {"name": "Jobs keep", "config": {**NO_MODELS, "output": {"format": "keep"}}}
    response = client.post("/presets/", headers=admin_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def one_at_a_time(client, admin_headers):
    """One image in flight, so the job's current image is known."""
    before = client.get("/settings/", headers=admin_headers).json()["process_concurrency"]
    assert client.patch("/settings/", headers=admin_headers, json={"process_concurrency": 1}).status_code == 200
    yield
    client.patch("/settings/", headers=admin_headers, json={"process_concurrency": before})


class _Gate:
    """Holds the pipeline of chosen keys at a cancellation checkpoint until released."""

    def __init__(self, monkeypatch, hold: set[str]) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        real = image_pipeline.run_pipeline

        def gated(key, plan, token):
            if key in hold:
                self.entered.set()
                deadline = time.monotonic() + 15
                while not self.release.is_set() and time.monotonic() < deadline:
                    token.check()
                    time.sleep(0.01)
            return real(key, plan, token)

        monkeypatch.setattr(image_pipeline, "run_pipeline", gated)


def _put(fake_s3, keys: list[str]) -> None:
    for key in keys:
        fake_s3.objects[key] = {"Body": make_image(fmt="JPEG"), "ContentType": "image/jpeg"}


def _start(client, headers, prefix: str, preset_id: int):
    return client.post("/jobs/start", headers=headers, json={"source_prefix": prefix, "preset_id": preset_id})


def _job(client, headers, job_id: str) -> dict:
    response = client.get(f"/jobs/{job_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _wait_until_finished(client, headers, job_id: str) -> dict:
    def finished():
        job = _job(client, headers, job_id)
        return job if job["status"] in ("completed", "stopped", "failed") else None

    return wait_for(finished, "the job to finish")


def _history(client, headers, job_id: str) -> dict:
    def row():
        rows = client.get("/activity/batch-history", headers=headers, params={"limit": 100}).json()
        return next((r for r in rows if r["job_id"] == job_id), None)

    return wait_for(row, "the job's history row")


def _images(client, headers, prefix: str) -> dict[str, dict]:
    body = client.get("/images/", headers=headers, params={"search": prefix, "page_size": 100}).json()
    return {i["source_key"]: i for g in body["items"] for i in g["images"]}


def test_a_job_processes_its_prefix_and_is_recorded_in_the_history(client, admin_headers, fake_s3, preset_id):
    prefix = "images/jobrun/"
    keys = [f"{prefix}{name}.jpg" for name in "abc"]
    _put(fake_s3, keys)
    _put(fake_s3, ["images/jobother/untouched.jpg"])  # outside the job's prefix

    started = _start(client, admin_headers, prefix, preset_id)
    assert started.status_code == 202, started.text
    job_id = started.json()["job_id"]
    assert (started.json()["source_prefix"], started.json()["preset_id"]) == (prefix, preset_id)

    job = _wait_until_finished(client, admin_headers, job_id)
    assert (job["status"], job["total"], job["processed"], job["failed"], job["skipped"]) == ("completed", 3, 3, 0, 0)
    assert job["progress_pct"] == 100.0 and job["errors"] == [] and job["current_key"] is None

    # The job discovered the images itself (no sync) and wrote one output per image.
    images = _images(client, admin_headers, prefix)
    assert set(images) == set(keys)
    assert all(i["status"] == "processed" and i["preset_id"] == preset_id for i in images.values())
    assert all(f"processed/{key}" in fake_s3.objects for key in keys)
    assert "processed/images/jobother/untouched.jpg" not in fake_s3.objects

    row = _history(client, admin_headers, job_id)
    assert (row["status"], row["total"], row["processed"], row["failed"], row["skipped"]) == ("completed", 3, 3, 0, 0)
    assert row["source_prefix"] == prefix and row["elapsed_seconds"] is not None

    assert job_id in {j["job_id"] for j in client.get("/jobs/", headers=admin_headers).json()}
    stats = client.get("/stats/", headers=admin_headers).json()
    assert stats["job_running"] is False

    # A second run over the same prefix has nothing left to do.
    again = _start(client, admin_headers, prefix, preset_id).json()["job_id"]
    rerun = _wait_until_finished(client, admin_headers, again)
    assert (rerun["status"], rerun["total"], rerun["processed"], rerun["skipped"]) == ("completed", 0, 0, 3)

    assert client.delete(f"/jobs/{again}", headers=admin_headers).status_code == 204
    assert client.get(f"/jobs/{again}", headers=admin_headers).status_code == 404
    assert client.delete(f"/jobs/{again}", headers=admin_headers).status_code == 404


def test_a_failing_image_is_counted_and_reported_without_failing_the_job(client, admin_headers, fake_s3, preset_id):
    prefix = "images/jobfail/"
    _put(fake_s3, [f"{prefix}good.jpg"])
    fake_s3.objects[f"{prefix}broken.jpg"] = {"Body": b"not an image", "ContentType": "image/jpeg"}

    job_id = _start(client, admin_headers, prefix, preset_id).json()["job_id"]
    job = _wait_until_finished(client, admin_headers, job_id)

    assert (job["status"], job["processed"], job["failed"]) == ("completed", 1, 1)
    (error,) = job["errors"]
    assert error == {"key": f"{prefix}broken.jpg", "error": "The file is not a valid JPEG, PNG or WebP image"}
    assert _history(client, admin_headers, job_id)["failed"] == 1


def test_only_one_job_runs_at_a_time_and_stop_ends_it(client, admin_headers, fake_s3, preset_id, monkeypatch):
    prefix = "images/jobstop/"
    keys = [f"{prefix}{n}.jpg" for n in range(4)]
    _put(fake_s3, keys)
    gate = _Gate(monkeypatch, set(keys))

    try:
        job_id = _start(client, admin_headers, prefix, preset_id).json()["job_id"]
        assert gate.entered.wait(timeout=15)
        running = _job(client, admin_headers, job_id)
        assert running["status"] == "running" and running["current_key"] in keys
        assert client.get("/stats/", headers=admin_headers).json()["job_running"] is True

        # While it runs: no second job, no sync, no delete, no database reset.
        refused = _start(client, admin_headers, prefix, preset_id)
        assert refused.status_code == 409 and "already running" in refused.json()["detail"]
        assert client.post("/images/sync", headers=admin_headers).status_code == 409
        assert client.delete(f"/jobs/{job_id}", headers=admin_headers).status_code == 409
        reset = client.post("/settings/reset-db", headers=admin_headers, json={**STEP_UP, "confirm": "RESET"})
        assert reset.status_code == 409 and "batch job" in reset.json()["detail"]

        stopped = client.post(f"/jobs/{job_id}/stop", headers=admin_headers)
        assert stopped.status_code == 200
        job = _wait_until_finished(client, admin_headers, job_id)
    finally:
        gate.release.set()

    assert (job["status"], job["processed"], job["total"]) == ("stopped", 0, 4)
    assert job["errors"] and all(e["error"] == "Aborted (job stopped)" for e in job["errors"])
    assert _history(client, admin_headers, job_id)["status"] == "stopped"
    assert not any(key.startswith("processed/images/jobstop/") for key in fake_s3.objects)

    images = _images(client, admin_headers, prefix)
    assert not any(i["status"] == "processed" or i["is_processing"] for i in images.values())
    aborted = [i for i in images.values() if i["status"] == "failed"]
    assert aborted and all(i["error_message"] == "Aborted by user" for i in aborted)

    # Stopping again changes nothing; a finished job no longer blocks the next one or a sync.
    assert client.post(f"/jobs/{job_id}/stop", headers=admin_headers).json()["status"] == "stopped"
    assert client.post(f"/jobs/{job_id}/skip", headers=admin_headers).status_code == 409
    assert client.post("/images/sync", headers=admin_headers).status_code == 200
    assert client.get("/settings/", headers=admin_headers).status_code == 200  # the refused reset left the DB alone
    assert _images(client, admin_headers, prefix)


def test_skip_aborts_the_current_image_and_the_job_moves_on(
    client, admin_headers, fake_s3, preset_id, monkeypatch, one_at_a_time
):
    prefix = "images/jobskip/"
    first, second = f"{prefix}a.jpg", f"{prefix}b.jpg"
    _put(fake_s3, [first, second])
    gate = _Gate(monkeypatch, {first})

    try:
        job_id = _start(client, admin_headers, prefix, preset_id).json()["job_id"]
        assert gate.entered.wait(timeout=15)
        assert _job(client, admin_headers, job_id)["current_key"] == first

        skipped = client.post(f"/jobs/{job_id}/skip", headers=admin_headers)
        assert skipped.status_code == 200, skipped.text
        job = _wait_until_finished(client, admin_headers, job_id)
    finally:
        gate.release.set()

    assert (job["status"], job["total"], job["processed"], job["skipped"], job["failed"]) == ("completed", 2, 1, 1, 0)
    assert job["errors"] == [{"key": first, "error": "Skipped by user"}]
    images = _images(client, admin_headers, prefix)
    assert (images[first]["status"], images[first]["error_message"]) == ("failed", "Aborted by user")
    assert images[second]["status"] == "processed"
    assert f"processed/{second}" in fake_s3.objects and f"processed/{first}" not in fake_s3.objects

    log = client.get("/activity/", headers=admin_headers, params={"search": job_id, "limit": 50}).json()
    assert {"job.start", "job.skip"} <= {entry["event_type"] for entry in log}


def test_job_requests_are_validated(client, admin_headers, preset_id):
    def start(**body):
        return client.post("/jobs/start", headers=admin_headers, json=body)

    assert start(source_prefix="elsewhere/").status_code == 400  # outside the source prefix
    assert start(source_prefix="images/../backup/").status_code == 400
    assert start(output_prefix="images/out/").status_code == 400  # outside the output prefix
    assert start(source_prefix="images/x y/").status_code == 422
    assert start(preset_id=0).status_code == 422
    assert start(preset_id=999_999, source_prefix="images/jobnone/").status_code == 400

    for path in ("/jobs/no-such-job/stop", "/jobs/no-such-job/skip"):
        assert client.post(path, headers=admin_headers).status_code == 404
    assert client.get("/jobs/no-such-job", headers=admin_headers).status_code == 404
    assert client.get("/jobs/no-such-job/stream", headers=admin_headers).status_code == 404
    assert client.get("/jobs/running", headers=admin_headers).status_code == 404  # not an endpoint: a job id
