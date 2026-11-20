"""Behavioural settings edited at runtime: validation, step-up tier, and effect at use time."""

import json

import pytest
from PIL import Image

from app.config import settings
from tests.conftest import login, make_image

STEP_UP = {"admin_password": "step-up-password"}
RUNTIME_DEFAULTS = {"max_upload_mb": 20, "max_remote_fetch_mb": 20, "max_image_megapixels": 80}
ADMIN_DEFAULTS = {
    "session_minutes": 720,
    "login_max_attempts": 3,  # LOGIN_MAX_ATTEMPTS in conftest
    "login_lockout_minutes": 15,
    "s3_object_acl": "",
    "presign_expires_seconds": 3600,
}


@pytest.fixture
def restore_settings(client, admin_headers):
    yield
    assert client.patch("/settings/", headers=admin_headers, json=RUNTIME_DEFAULTS).status_code == 200
    response = client.patch("/settings/admin", headers=admin_headers, json={**ADMIN_DEFAULTS, **STEP_UP})
    assert response.status_code == 200


def test_get_settings_returns_every_field(client, admin_headers):
    body = client.get("/settings/", headers=admin_headers).json()
    assert {**RUNTIME_DEFAULTS, **ADMIN_DEFAULTS}.items() <= body.items()
    assert body["openai_image_model"] == "gpt-image-1.5"
    assert body["gemini_image_model"] == "gemini-3.1-flash-image-preview"


@pytest.mark.parametrize(
    "patch",
    [
        {"max_upload_mb": 0},
        {"max_upload_mb": 201},
        {"max_remote_fetch_mb": 0},
        {"max_image_megapixels": 501},
        {"openai_image_model": ""},
        {"openai_image_model": "gpt image"},
        {"gemini_image_model": "x" * 101},
        {"gemini_image_model": "models/gemini;rm"},
    ],
)
def test_runtime_validation(client, admin_headers, patch):
    assert client.patch("/settings/", headers=admin_headers, json=patch).status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"session_minutes": 4},
        {"session_minutes": 10081},
        {"login_max_attempts": 0},
        {"login_max_attempts": 101},
        {"login_lockout_minutes": 1441},
        {"s3_object_acl": "public-read-write"},
        {"presign_expires_seconds": 59},
        {"presign_expires_seconds": 604801},
    ],
)
def test_admin_validation(client, admin_headers, patch):
    assert client.patch("/settings/admin", headers=admin_headers, json={**patch, **STEP_UP}).status_code == 422


def test_model_names_are_runtime_settings(client, admin_headers, restore_settings):
    patch = {"openai_image_model": "gpt-image-1", "gemini_image_model": "models/gemini-2.5:flash_image"}
    response = client.patch("/settings/", headers=admin_headers, json=patch)
    assert response.status_code == 200
    assert patch.items() <= response.json().items()
    client.patch(
        "/settings/",
        headers=admin_headers,
        json={"openai_image_model": "gpt-image-1.5", "gemini_image_model": "gemini-3.1-flash-image-preview"},
    )


@pytest.mark.parametrize("field", list(ADMIN_DEFAULTS))
def test_security_and_storage_fields_need_the_step_up(client, admin_headers, field):
    value = ADMIN_DEFAULTS[field]
    # Not accepted by the runtime endpoint at all...
    assert client.patch("/settings/", headers=admin_headers, json={field: value}).status_code == 422
    # ...and the admin endpoint needs the admin password.
    response = client.patch("/settings/admin", headers=admin_headers, json={field: value, "admin_password": "no"})
    assert response.status_code == 403
    assert client.patch("/settings/admin", headers=admin_headers, json={field: value}).status_code == 422


def test_non_admins_cannot_change_limits(client, admin_headers):
    client.post(
        "/users/", headers=admin_headers, json={"username": "limits_user", "password": "limits-password-1", **STEP_UP}
    )
    headers = login(client, "limits_user", "limits-password-1")
    assert client.patch("/settings/", headers=headers, json={"max_upload_mb": 5}).status_code == 403
    assert client.patch("/settings/admin", headers=headers, json={"session_minutes": 30, **STEP_UP}).status_code == 403


def test_session_minutes_apply_to_new_tokens(client, admin_headers, restore_settings):
    response = client.patch("/settings/admin", headers=admin_headers, json={"session_minutes": 30, **STEP_UP})
    assert response.status_code == 200
    login_response = client.post("/auth/login", json={"username": "admin", "password": "bootstrap-password"})
    assert login_response.json()["expires_in"] == 30 * 60


def test_rate_limiter_follows_changed_limits(client, admin_headers, restore_settings):
    def attempt(password: str) -> int:
        return client.post("/auth/login", json={"username": "admin", "password": password}).status_code

    response = client.patch("/settings/admin", headers=admin_headers, json={"login_max_attempts": 5, **STEP_UP})
    assert response.status_code == 200
    assert [attempt("wrong") for _ in range(4)] == [401] * 4
    assert attempt("bootstrap-password") == 200  # 4 failures < 5: still allowed

    for _ in range(4):
        attempt("wrong")
    response = client.patch("/settings/admin", headers=admin_headers, json={"login_max_attempts": 2, **STEP_UP})
    assert response.status_code == 200
    assert attempt("bootstrap-password") == 429  # the lower limit applies at check time


def test_max_image_pixels_follows_the_setting(client, admin_headers, restore_settings):
    assert Image.MAX_IMAGE_PIXELS == 80_000_000
    assert client.patch("/settings/", headers=admin_headers, json={"max_image_megapixels": 1}).status_code == 200
    assert Image.MAX_IMAGE_PIXELS == 1_000_000

    config = {"background": {"remove": False}, "upscale": {"enabled": False}, "canvas": {"enabled": False}}
    response = client.post(
        "/playground/",
        headers=admin_headers,
        data={"config": json.dumps(config)},
        files={"file": ("big.png", make_image((1500, 1500)), "image/png")},
    )
    assert response.status_code == 400  # 2.25 MP is a decompression bomb under a 1 MP limit

    client.patch("/settings/", headers=admin_headers, json={"max_image_megapixels": 80})
    assert Image.MAX_IMAGE_PIXELS == 80_000_000


def test_presign_expiry_and_object_acl_apply(client, admin_headers, fake_s3, monkeypatch, restore_settings):
    from app.core import net

    async def safe_get(url, *, max_bytes, require_image=False, **_options):
        return net.FetchResult(make_image(), "image/png")

    monkeypatch.setattr(net, "safe_get", safe_get)
    patch = {"presign_expires_seconds": 120, "s3_object_acl": "private", **STEP_UP}
    assert client.patch("/settings/admin", headers=admin_headers, json=patch).status_code == 200

    body = client.post(
        "/imports/", headers=admin_headers, json={"urls": ["https://a.example/acl.png"], "folder": "acl/"}
    ).json()
    (imported,) = body["imported"]
    assert fake_s3.objects[imported["key"]]["ACL"] == "private"

    listing = client.get("/images/", headers=admin_headers, params={"search": "images/acl/"}).json()
    (image,) = [img for group in listing["items"] for img in group["images"]]
    assert "X-Amz-Expires=120" in image["source_url"]

    assert (
        client.patch("/settings/admin", headers=admin_headers, json={"s3_object_acl": "", **STEP_UP}).status_code == 200
    )
    body = client.post(
        "/imports/", headers=admin_headers, json={"urls": ["https://a.example/acl.png"], "folder": "acl/"}
    ).json()
    assert "ACL" not in fake_s3.objects[body["imported"][0]["key"]]


def test_environment_is_read_only_and_leaks_no_secrets(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://storage-user:storage-pass@minio:9000/some/path?x=1")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "https://cdn.example.com")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-openai-secret")
    monkeypatch.setattr(settings, "s3_access_key", "AKIA-storage-access")
    monkeypatch.setattr(settings, "s3_secret_key", "storage-secret-key")

    client.post(
        "/users/", headers=admin_headers, json={"username": "env_viewer", "password": "viewer-password-1", **STEP_UP}
    )
    response = client.get("/settings/environment", headers=login(client, "env_viewer", "viewer-password-1"))

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "app_name": "Bucket Studio",
        "s3_bucket": "test-bucket",
        "s3_endpoint_host": "minio:9000",
        "s3_public_endpoint_host": "cdn.example.com",
        "openai_configured": True,
        "gemini_configured": False,
        "api_docs_enabled": False,
        "models_dir_writable": True,
        "version": "0.1.0",
    }
    text = response.text
    for secret in (
        "sk-test-openai-secret",
        "storage-user",
        "storage-pass",
        settings.jwt_secret,
        settings.auth_password,
        settings.admin_password,
        settings.api_key,
        "AKIA-storage-access",
        "storage-secret-key",
    ):
        assert secret not in text
    assert client.get("/settings/environment").status_code == 401
