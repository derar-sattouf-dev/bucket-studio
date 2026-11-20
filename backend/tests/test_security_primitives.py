"""Password hashing, login throttling, JWT."""

import jwt
import pytest

from app.core import rate_limit
from app.core.jwt import create_token, verify_token
from app.core.passwords import hash_password, validate_password_strength, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)
    assert not verify_password("anything", None)


@pytest.mark.parametrize("password", ["short", "x" * 73])
def test_password_policy_rejects(password):
    with pytest.raises(ValueError):
        validate_password_strength(password)


def test_rate_limit_locks_after_max_attempts():
    limits = rate_limit.LoginLimits(max_attempts=3, lockout_minutes=15)
    for _ in range(3):
        assert rate_limit.reserve_login("1.2.3.4", "bob", limits) == 0
    assert rate_limit.reserve_login("1.2.3.4", "bob", limits) > 0
    # Limits are read at check time: a higher limit unlocks immediately.
    assert rate_limit.reserve_login("1.2.3.4", "bob", rate_limit.LoginLimits(5, 15)) == 0
    # another username from another IP is unaffected
    assert rate_limit.reserve_login("5.6.7.8", "alice", limits) == 0


def test_rate_limit_counts_attempts_before_they_are_checked():
    """Parallel guesses are all counted up front, so a burst cannot exceed the limit."""
    limits = rate_limit.LoginLimits(max_attempts=3, lockout_minutes=15)
    allowed = [rate_limit.reserve_login("9.9.9.9", "bob", limits) == 0 for _ in range(10)]
    assert allowed.count(True) == 3


def test_a_successful_login_forgives_its_attempt():
    limits = rate_limit.LoginLimits(max_attempts=2, lockout_minutes=15)
    for _ in range(5):
        assert rate_limit.reserve_login("8.8.8.8", "carol", limits) == 0
        rate_limit.forgive_login("8.8.8.8", "carol")
    assert rate_limit._attempts == {}  # nothing is kept for idle clients


def test_jwt_roundtrip_and_tamper():
    token = create_token("alice", 60)
    assert verify_token(token) == "alice"
    assert jwt.decode(token, options={"verify_signature": False})["iss"] == "bucket-studio"
    assert verify_token(token[:-2] + "xx") is None
    assert verify_token("not-a-token") is None


def test_step_up_password_guessing_is_throttled(client, admin_headers):
    wrong = {"admin_password": "not-the-admin-password"}
    for _ in range(5):
        assert client.post("/settings/verify-admin", headers=admin_headers, json=wrong).status_code == 403
    locked = client.post("/settings/verify-admin", headers=admin_headers, json=wrong)
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0


def test_parallel_login_guesses_cannot_exceed_the_limit(client):
    """LOGIN_MAX_ATTEMPTS is 3 in the test environment; every attempt past it is refused before checking."""
    codes = [
        client.post("/auth/login", json={"username": "admin", "password": f"guess-{i}"}).status_code for i in range(6)
    ]
    assert codes == [401, 401, 401, 429, 429, 429]


def test_public_error_never_exposes_library_text():
    from botocore.exceptions import ClientError

    from app.core.image_pipeline import public_error
    from app.core.processor import PresetError

    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "arn:aws:s3:::secret-bucket/x"}}, "PutObject")
    assert public_error(denied) == "Storage error (AccessDenied)"
    assert "secret" not in public_error(RuntimeError("connect to internal-host.lan:9000 failed (secret)"))
    assert public_error(PresetError("A transparent canvas needs png")) == "A transparent canvas needs png"


def test_only_jpeg_png_and_webp_are_decoded():
    import io

    from PIL import Image, UnidentifiedImageError

    from app.core.imaging import probe

    for fmt in ("GIF", "BMP", "TIFF"):
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format=fmt)
        with pytest.raises(UnidentifiedImageError):
            probe(buf.getvalue())


def test_size_limit_search_finds_a_fitting_quality():
    import io

    import numpy as np
    from PIL import Image

    from app.core.imaging import ImageTooLarge, encode

    noise = Image.fromarray(np.random.default_rng(0).integers(0, 255, (300, 300, 3), dtype=np.uint8))
    full = encode(noise, "jpeg", 90)
    limit = len(full) // 2
    fitted = encode(noise, "jpeg", 90, max_bytes=limit)
    assert len(fitted) <= limit and Image.open(io.BytesIO(fitted)).size == (300, 300)
    with pytest.raises(ImageTooLarge):
        encode(noise, "jpeg", 90, max_bytes=500)


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_prefix": ""},  # every key in the bucket would be a source
        {"source_prefix": "images"},  # no trailing slash
        {"output_prefix": "images/"},  # same as the source prefix
        {"backup_prefix": "images/backup/"},  # nested inside the source prefix
        {"admin_password": "short"},
        {"api_key": "short"},
    ],
)
def test_unsafe_environment_values_are_refused_at_startup(overrides):
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_a_cutout_saved_as_jpeg_is_flattened_onto_the_canvas_colour():
    import io

    from PIL import Image

    from app.core.preset_config import PresetConfig
    from app.core.processor import process_image

    buf = io.BytesIO()
    Image.new("RGBA", (40, 40), (0, 0, 0, 0)).save(buf, format="PNG")
    config = PresetConfig.model_validate({"canvas": {"background": "#0000FF"}, "output": {"format": "jpeg"}})
    out = Image.open(io.BytesIO(process_image(buf.getvalue(), config, source_format="png").data))
    r, g, b = out.getpixel((20, 20))
    assert b > 240 and r < 15 and g < 15
