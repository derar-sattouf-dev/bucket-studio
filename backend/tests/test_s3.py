"""S3 helpers: browser-facing URL signing and object ACLs."""

from urllib.parse import urlsplit

import pytest

from app.config import settings
from app.core import s3


@pytest.fixture
def fresh_clients():
    s3.get_s3_client.cache_clear()
    s3.get_presign_client.cache_clear()
    s3._presign_cache.clear()
    yield
    s3.get_s3_client.cache_clear()
    s3.get_presign_client.cache_clear()
    s3._presign_cache.clear()


def test_presigned_urls_use_the_public_endpoint(monkeypatch, fresh_clients):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "http://localhost:9000")

    url = s3.presign_get("images/a.jpg", 3600)

    assert urlsplit(url).netloc == "localhost:9000"
    assert "X-Amz-Signature=" in url
    assert s3.get_s3_client().meta.endpoint_url == "http://minio:9000"


def test_presigned_urls_default_to_the_storage_endpoint(monkeypatch, fresh_clients):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "")
    assert urlsplit(s3.presign_get("images/a.jpg", 3600)).netloc == "minio:9000"


def test_presign_cache_follows_the_expiry(monkeypatch, fresh_clients):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "")
    assert "X-Amz-Expires=3600" in s3.presign_get("images/a.jpg", 3600)
    assert "X-Amz-Expires=120" in s3.presign_get("images/a.jpg", 120)


class _RecordingS3:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def copy_object(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_object_acl_is_optional():
    client = _RecordingS3()
    s3.put_image(client, "bucket", "a.jpg", b"img", "image/jpeg", acl="public-read")
    s3.copy_object(client, "bucket", "a.jpg", "backup/a.jpg")
    s3.put_image(client, "bucket", "b.jpg", b"img", "image/jpeg", acl="")
    assert client.calls[0]["ACL"] == "public-read"
    assert "ACL" not in client.calls[1]
    assert "ACL" not in client.calls[2]
