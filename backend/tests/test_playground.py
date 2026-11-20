"""POST /playground and /playground/from-url with presets that need no ML models."""

import io
import json

import pytest
from PIL import Image

from app.core import net
from tests.conftest import make_image

NO_MODELS = {
    "background": {"remove": False},
    "upscale": {"method": "lanczos"},
    "canvas": {"enabled": True, "width": 128, "height": 96, "background": "transparent"},
    "output": {"format": "png"},
}


def _post(client, headers, data: dict, content: bytes, filename: str = "sample.png"):
    return client.post("/playground/", headers=headers, data=data, files={"file": (filename, content, "image/png")})


def test_upload_with_ad_hoc_config(client, admin_headers):
    response = _post(
        client, admin_headers, {"config": json.dumps(NO_MODELS)}, make_image(background=None, color=(0, 0, 255, 255))
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="sample_processed.png"'
    assert int(response.headers["x-processing-ms"]) >= 0
    img = Image.open(io.BytesIO(response.content))
    assert (img.format, img.mode, img.size) == ("PNG", "RGBA", (128, 96))


def test_upload_with_stored_preset(client, admin_headers):
    config = {**NO_MODELS, "canvas": {"enabled": False}, "output": {"format": "keep"}}
    preset = client.post("/presets/", headers=admin_headers, json={"name": "Playground keep", "config": config}).json()

    response = _post(client, admin_headers, {"preset_id": str(preset["id"])}, make_image(fmt="JPEG"), "pic.jpeg")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"] == 'attachment; filename="pic_processed.jpeg"'


@pytest.mark.parametrize(
    ("data", "status"),
    [
        ({}, 422),  # neither preset_id nor config
        ({"preset_id": "1", "config": "{}"}, 422),  # both
        ({"config": "{not json"}, 422),
        (
            {
                "config": json.dumps(
                    {"canvas": {"enabled": True, "background": "transparent"}, "output": {"format": "jpeg"}}
                )
            },
            422,
        ),
        ({"preset_id": "999999"}, 404),
        ({"config": json.dumps({**NO_MODELS, "ai": {"engine": "openai"}})}, 422),  # no OPENAI_API_KEY
        ({"config": json.dumps(NO_MODELS), "engine": "gemini"}, 422),  # no GEMINI_API_KEY
        ({"config": json.dumps(NO_MODELS), "engine": "magic"}, 422),
    ],
)
def test_invalid_requests(client, admin_headers, data, status):
    assert _post(client, admin_headers, data, make_image()).status_code == status


def test_input_must_decode(client, admin_headers):
    response = _post(client, admin_headers, {"config": json.dumps(NO_MODELS)}, b"GIF89a but not really")
    assert response.status_code == 400


def test_transparent_canvas_on_jpeg_source_with_keep_is_422(client, admin_headers):
    config = {**NO_MODELS, "output": {"format": "keep"}}
    response = _post(client, admin_headers, {"config": json.dumps(config)}, make_image(fmt="JPEG"), "a.jpg")
    assert response.status_code == 422


def test_upload_size_limit_follows_the_setting(client, admin_headers):
    oversized = make_image() + b"\0" * (1024 * 1024)
    assert _post(client, admin_headers, {"config": json.dumps(NO_MODELS)}, oversized).status_code == 200
    assert client.patch("/settings/", headers=admin_headers, json={"max_upload_mb": 1}).status_code == 200
    try:
        assert _post(client, admin_headers, {"config": json.dumps(NO_MODELS)}, oversized).status_code == 413
    finally:
        client.patch("/settings/", headers=admin_headers, json={"max_upload_mb": 20})


def test_from_url(client, admin_headers, monkeypatch):
    async def safe_get(url, *, max_bytes, require_image=False, **_options):
        assert require_image is True
        if "internal" in url:
            raise net.UnsafeURLError("private")
        return net.FetchResult(make_image(fmt="WEBP"), "image/webp")

    monkeypatch.setattr(net, "safe_get", safe_get)
    config = {**NO_MODELS, "output": {"format": "keep"}}

    response = client.post(
        "/playground/from-url",
        headers=admin_headers,
        json={"url": "https://img.example.com/dir/shoe.webp?x=1", "config": config},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["content-disposition"] == 'attachment; filename="shoe_processed.webp"'

    blocked = client.post(
        "/playground/from-url", headers=admin_headers, json={"url": "http://internal.example/x.png", "config": config}
    )
    assert blocked.status_code == 400
    both = client.post(
        "/playground/from-url",
        headers=admin_headers,
        json={"url": "https://img.example.com/a.png", "config": config, "preset_id": 1},
    )
    assert both.status_code == 422


def test_cors_exposes_playground_headers(client, admin_headers):
    response = _post(
        client,
        {**admin_headers, "Origin": "http://localhost:5173"},
        {"config": json.dumps(NO_MODELS)},
        make_image(),
    )
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "x-processing-ms" in exposed and "content-disposition" in exposed
