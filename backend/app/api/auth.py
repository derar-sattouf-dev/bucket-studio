"""Authentication routes: login (public) and current-user info. Logic lives in services/auth_service.py."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.schema import LoginRequest, LoginResponse, MeResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Behind a reverse proxy, run uvicorn with --proxy-headers and FORWARDED_ALLOW_IPS so
    # request.client reflects the real client address.
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    try:
        session = await auth_service.login(db, body.username, body.password, ip=_client_ip(request))
    except auth_service.LoginThrottled as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except auth_service.InvalidCredentials as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password") from exc
    return LoginResponse(token=session.token, expires_in=session.expires_in)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, is_admin=user.is_admin)
