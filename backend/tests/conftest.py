"""Test configuration.

Environment variables must be set before `app.config` is imported, because settings are
read once at import time.
"""

import io
import os
import socket
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="bucket-studio-tests-")

os.environ["BUCKET_STUDIO_DOTENV"] = "0"  # never read a developer's local .env
os.environ.update(
    {
        "DATA_DIR": os.path.join(_TMP, "data"),
        "MODELS_DIR": os.path.join(_TMP, "models"),
        "JWT_SECRET": "test-secret-" + "x" * 40,
        "AUTH_USERNAME": "admin",
        "AUTH_PASSWORD": "bootstrap-password",
        "ADMIN_PASSWORD": "step-up-password",
        "API_KEY": "integration-key-for-tests",
        "S3_ENDPOINT_URL": "http://127.0.0.1:1",
        "S3_ACCESS_KEY": "test",
        "S3_SECRET_KEY": "test",
        "S3_AUTO_CREATE_BUCKET": "false",
        "S3_BUCKET": "test-bucket",
        "SOURCE_PREFIX": "images/",
        "OUTPUT_PREFIX": "processed/",
        "BACKUP_PREFIX": "backup/",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
        "SYNC_INTERVAL_MINUTES": "0",
        "LOGIN_MAX_ATTEMPTS": "3",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.core import model_store, processor, rate_limit, s3  # noqa: E402
from tests.fakes import FakeS3  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    """Tests never download or load ML models (and never touch the network for them)."""

    def fail(*_args, **_kwargs):
        raise AssertionError("tests must not download or load ML models")

    monkeypatch.setattr(model_store, "_download", fail)
    monkeypatch.setattr(processor, "remove_background", fail)
    monkeypatch.setattr(processor, "_esrgan_2x", fail)


class NetworkBlocked(RuntimeError):
    """A test tried to open a real network connection."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Tests never hit the network: every outgoing socket connection fails, whoever opens it.

    The in-process `TestClient` needs no sockets beyond the event loop's own socket pair, which is
    created connected and never calls `connect`. Unix sockets (local IPC) stay allowed.
    """

    def guarded(original):
        def connect(self, address, *args):
            if self.family != getattr(socket, "AF_UNIX", None):
                raise NetworkBlocked(f"tests must not open network connections (tried {address!r})")
            return original(self, address, *args)

        return connect

    monkeypatch.setattr(socket.socket, "connect", guarded(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(socket.socket.connect_ex))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    rate_limit.clear_all()
    yield
    rate_limit.clear_all()


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def admin_headers(client) -> dict[str, str]:
    return login(client, "admin", "bootstrap-password")


@pytest.fixture
def fake_s3(monkeypatch) -> FakeS3:
    """Route every S3 call (operations and URL signing) to an in-memory bucket."""
    fake = FakeS3()
    s3.get_s3_client.cache_clear()
    s3.get_presign_client.cache_clear()
    s3._presign_cache.clear()
    monkeypatch.setattr(s3, "_make_client", lambda _endpoint: fake)
    yield fake
    s3.get_s3_client.cache_clear()
    s3.get_presign_client.cache_clear()
    s3._presign_cache.clear()


def wait_for(condition, what: str, timeout: float = 20):
    """Poll `condition` until it returns something truthy (background work runs on the app's loop)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(f"{what} did not happen in time")


def make_image(
    size: tuple[int, int] = (64, 48),
    fmt: str = "PNG",
    color: tuple[int, ...] = (200, 30, 30),
    background: tuple[int, ...] | None = (255, 255, 255),
    margin: int = 8,
) -> bytes:
    """An encoded test image: a coloured rectangle on a plain background (None = transparent)."""
    mode = "RGBA" if background is None or len(color) == 4 else "RGB"
    img = Image.new(mode, size, background or (0, 0, 0, 0))
    img.paste(color, (margin, margin, size[0] - margin, size[1] - margin))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()
