"""POST /imports: SSRF-guarded fetch (mocked), Pillow verification, safe names, DB insertion."""

import pytest

from app.core import net
from tests.conftest import make_image


@pytest.fixture
def remote(monkeypatch) -> dict[str, bytes | Exception]:
    responses: dict[str, bytes | Exception] = {}

    async def safe_get(url, *, max_bytes, require_image=False, **_options):
        assert require_image is True
        assert max_bytes == 20 * 1024 * 1024  # MAX_REMOTE_FETCH_MB default
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        return net.FetchResult(content=value, content_type="image/png")

    monkeypatch.setattr(net, "safe_get", safe_get)
    return responses


def _listed_keys(client, headers, search: str) -> dict[str, dict]:
    body = client.get("/images/", headers=headers, params={"search": search, "page_size": 100}).json()
    return {img["source_key"]: img for group in body["items"] for img in group["images"]}


def test_import_stores_verified_images_with_safe_unique_names(client, admin_headers, fake_s3, remote):
    fake_s3.objects["images/imp/a/photo.png"] = {"Body": b"existing", "ContentType": "image/png"}
    remote["https://cdn.example.com/x/photo.png"] = make_image(fmt="PNG")
    remote["https://other.example.com/photo.png?v=2"] = make_image(fmt="PNG")
    remote["https://cdn.example.com/%E2%9C%93%20my%20pic!.jpeg"] = make_image(fmt="JPEG")
    remote["https://cdn.example.com/actually-png.jpg"] = make_image(fmt="PNG")
    remote["https://cdn.example.com/notes.png"] = b"definitely not an image"
    remote["https://cdn.example.com/anim.gif"] = make_image(fmt="GIF")
    remote["https://cdn.example.com/private.png"] = net.UnsafeURLError("private")
    remote["https://cdn.example.com/down.png"] = net.FetchError("HTTP 500")

    response = client.post("/imports/", headers=admin_headers, json={"urls": list(remote), "folder": "imp/a/"})

    assert response.status_code == 200, response.text
    body = response.json()
    imported = {item["url"]: item["key"] for item in body["imported"]}
    # Downloads run concurrently, so which of the two `photo.png` gets which free suffix is not fixed.
    photos = {
        imported.pop("https://cdn.example.com/x/photo.png"),
        imported.pop("https://other.example.com/photo.png?v=2"),
    }
    assert photos == {"images/imp/a/photo-2.png", "images/imp/a/photo-3.png"}
    assert imported == {
        "https://cdn.example.com/%E2%9C%93%20my%20pic!.jpeg": "images/imp/a/my-pic.jpg",
        "https://cdn.example.com/actually-png.jpg": "images/imp/a/actually-png.png",
    }
    errors = {item["url"]: item["error"] for item in body["failed"]}
    assert errors == {
        "https://cdn.example.com/notes.png": "Not a valid image (use JPEG, PNG or WebP)",
        "https://cdn.example.com/anim.gif": "Not a valid image (use JPEG, PNG or WebP)",
        "https://cdn.example.com/private.png": "URL not allowed",
        "https://cdn.example.com/down.png": "Could not fetch image",
    }

    assert fake_s3.objects["images/imp/a/photo.png"]["Body"] == b"existing"  # never overwritten
    assert fake_s3.objects["images/imp/a/my-pic.jpg"]["ContentType"] == "image/jpeg"
    listed = _listed_keys(client, admin_headers, "images/imp/a/")
    imported_keys = set(imported.values()) | photos
    assert imported_keys <= set(listed)
    assert all(listed[k]["status"] == "pending" and listed[k]["group_key"] == "imp" for k in imported_keys)


@pytest.mark.parametrize(
    "body",
    [
        {"urls": [], "folder": ""},
        {"urls": ["https://a.example/x.png"] * 101, "folder": ""},
        {"urls": ["https://a.example/x.png"], "folder": "../escape/"},
        {"urls": ["https://a.example/x.png"], "folder": "a/./b/"},
        {"urls": ["https://a.example/x.png"], "folder": "/abs/"},
        {"urls": ["https://a.example/x.png"], "folder": "no-trailing-slash"},
        {"urls": ["https://a.example/x.png"], "folder": "sp ace/"},
        {"urls": ["https://a.example/" + "x" * 2050], "folder": ""},
    ],
)
def test_invalid_import_requests(client, admin_headers, body):
    assert client.post("/imports/", headers=admin_headers, json=body).status_code == 422
