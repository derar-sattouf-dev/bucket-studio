"""FastAPI application entry point."""

import asyncio
import logging
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.api import activity as activity_api
from app.api import auth as auth_api
from app.api import images as images_api
from app.api import imports as imports_api
from app.api import jobs as jobs_api
from app.api import playground as playground_api
from app.api import presets as presets_api
from app.api import settings as settings_api
from app.api import stats as stats_api
from app.api import users as users_api
from app.config import settings
from app.core import model_store, net
from app.core.auth import get_current_user
from app.db.crud import recover_stuck_images
from app.db.session import AsyncSessionLocal, init_db
from app.scheduler import shutdown_scheduler, start_scheduler
from app.services.preset_service import seed_presets
from app.services.settings_service import apply_image_limits, get_runtime_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Decompression-bomb protection for every image decode in the process. This is the env default,
# in force until the stored settings are loaded in `lifespan`; `apply_image_limits` then sets the
# runtime value (`max_image_megapixels`), and again whenever the settings are changed.
Image.MAX_IMAGE_PIXELS = settings.max_image_megapixels * 1_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)


def _check_required_settings() -> None:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set — refusing to start (generate one with `openssl rand -hex 32`)")
    if not (settings.auth_username and settings.auth_password):
        logger.warning("[startup] AUTH_USERNAME / AUTH_PASSWORD not set — only DB users can log in")
    if not settings.admin_password:
        logger.warning("[startup] ADMIN_PASSWORD not set — admin-only actions are disabled")


async def _ensure_bucket() -> None:
    """Create the S3 bucket when S3_AUTO_CREATE_BUCKET is on (local MinIO). Retries while MinIO starts."""
    if not settings.s3_auto_create_bucket:
        return
    from botocore.exceptions import BotoCoreError, ClientError

    from app.core.s3 import get_s3_client

    def _create() -> bool:
        s3 = get_s3_client()
        try:
            s3.head_bucket(Bucket=settings.s3_bucket)
            return False
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket", "NotFound"):
                raise
        s3.create_bucket(Bucket=settings.s3_bucket)
        return True

    for attempt in range(1, 11):
        try:
            if await asyncio.to_thread(_create):
                logger.info("[startup] Created bucket '%s'", settings.s3_bucket)
            return
        except (BotoCoreError, ClientError) as exc:
            logger.warning("[startup] Bucket check failed (attempt %d/10): %s", attempt, type(exc).__name__)
            await asyncio.sleep(2)
    logger.error("[startup] Could not verify bucket '%s'", settings.s3_bucket)


async def _recover_stuck_images() -> None:
    async with AsyncSessionLocal() as db:
        recovered = await recover_stuck_images(db)
    if recovered:
        logger.info("[startup] Recovered %d stuck image(s) → pending", recovered)


async def _seed_presets() -> None:
    async with AsyncSessionLocal() as db:
        await seed_presets(db)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _check_required_settings()
    model_store.check_models_dir()
    await init_db()
    await _ensure_bucket()
    await _recover_stuck_images()
    await _seed_presets()

    async with AsyncSessionLocal() as db:
        rs = await get_runtime_settings(db)
    apply_image_limits(rs)
    start_scheduler(minutes=rs.sync_interval_minutes)
    yield
    shutdown_scheduler()
    await net.aclose()


app = FastAPI(
    title=f"{settings.app_name} API",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth uses the Authorization header, never cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    expose_headers=["Content-Disposition", "Retry-After", "X-Processing-Ms"],
    max_age=600,
)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "cross-origin",
}
_NO_STORE_PREFIXES = (
    "/images",
    "/jobs",
    "/auth",
    "/users",
    "/settings",
    "/activity",
    "/stats",
    "/presets",
    "/imports",
    "/playground",
)


@app.middleware("http")
async def response_headers_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.url.path.startswith(_NO_STORE_PREFIXES) and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


# Public
app.include_router(auth_api.router)

# Any signed-in user (admin-only endpoints add `require_admin` inside their router)
_authenticated = [Depends(get_current_user)]
for module in (
    settings_api,
    presets_api,
    jobs_api,
    images_api,
    imports_api,
    playground_api,
    stats_api,
    activity_api,
    users_api,
):
    app.include_router(module.router, dependencies=_authenticated)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}
