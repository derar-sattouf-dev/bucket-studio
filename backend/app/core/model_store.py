"""Where ML weights live, and their on-first-use download.

Everything goes under `settings.models_path` (`MODELS_DIR`, a volume in Docker):

* `u2net/` — rembg models. rembg reads `U2NET_HOME` when a session is created and verifies
  its own downloads; `prepare_rembg_home` must run before the first session.
* `RealESRGAN_x4plus.pth` — downloaded from the official release and SHA-256 verified,
  both after download and before every load.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

ESRGAN_FILENAME = "RealESRGAN_x4plus.pth"
_ESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
_ESRGAN_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
_DOWNLOAD_TIMEOUT_SECONDS = 120


def models_dir() -> Path:
    """The models directory, created on demand (owner-only permissions)."""
    path = settings.models_path
    path.mkdir(mode=0o750, parents=True, exist_ok=True)
    return path


def is_models_dir_writable() -> bool:
    """True if the models directory exists (or can be created) and is writable."""
    try:
        path = models_dir()
    except OSError:
        return False
    return os.access(path, os.W_OK | os.X_OK)


def check_models_dir() -> None:
    """Startup check: warn when models cannot be downloaded."""
    if not is_models_dir_writable():
        logger.warning("[startup] MODELS_DIR %s is not writable; models cannot be downloaded", settings.models_path)


def prepare_rembg_home() -> Path:
    """Point rembg at `<models_dir>/u2net`. Call before creating any rembg session."""
    home = models_dir() / "u2net"
    home.mkdir(mode=0o750, exist_ok=True)
    os.environ["U2NET_HOME"] = str(home)
    return home


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, dest: Path, sha256: str) -> None:
    """Download to a temp file next to `dest`, verify the checksum, then move into place."""
    logger.info("Downloading %s to %s", url, dest)
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with (
            os.fdopen(fd, "wb") as out,
            urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp,  # noqa: S310 — fixed https URL
        ):
            for block in iter(lambda: resp.read(1024 * 1024), b""):
                out.write(block)
        if _sha256_of(tmp_path) != sha256:
            raise RuntimeError(f"Downloaded {dest.name} failed SHA-256 verification")
        tmp_path.replace(dest)
    finally:
        tmp_path.unlink(missing_ok=True)


def esrgan_weights() -> Path:
    """Path to verified Real-ESRGAN x4plus weights, downloading them on first use."""
    path = models_dir() / ESRGAN_FILENAME
    if not path.exists():
        _download(_ESRGAN_URL, path, _ESRGAN_SHA256)
    if _sha256_of(path) != _ESRGAN_SHA256:
        raise RuntimeError(f"{path} failed SHA-256 verification; refusing to load it")
    return path
