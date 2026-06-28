from datetime import datetime
from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.integrations.telegram import TelegramInitDataError, validate_telegram_init_data
from app.modules.auth import AuthError, authenticate_telegram_user, logout, refresh_tokens
from app.modules.auth.rate_limit import check_auth_rate_limit, check_auth_rate_limit_by_telegram_id
from app.modules.auth.schemas import (
    RefreshResponse,
    TelegramAuthRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

REFRESH_TOKEN_COOKIE = "refresh_token"


def _set_refresh_cookie(
    response: Response,
    token: str,
    expires_at: datetime,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path=f"{settings.api_v1_prefix}/auth",
        expires=expires_at,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path=f"{settings.api_v1_prefix}/auth",
    )


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    request: Request,
    response: Response,
    payload: TelegramAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenResponse:
    """authenticate telegram user"""
    await check_auth_rate_limit(redis, request, settings.trust_proxy_headers)
    try:
        telegram_user = validate_telegram_init_data(
            init_data=payload.init_data,
            bot_token=settings.telegram_bot_token,
            max_age_seconds=settings.telegram_init_data_max_age_seconds,
        )
    except TelegramInitDataError as exc:
        logger.warning("telegram auth validation failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication data",
        ) from exc

    await check_auth_rate_limit_by_telegram_id(redis, telegram_user.telegram_id)
    token_response, refresh_token = await authenticate_telegram_user(db, telegram_user, settings)
    _set_refresh_cookie(response, refresh_token, token_response.refresh_token_expires_at, settings)
    return token_response


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_auth_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> RefreshResponse:
    """refresh auth tokens using the httpOnly cookie"""
    await check_auth_rate_limit(redis, request, settings.trust_proxy_headers)
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )
    try:
        refresh_response, new_refresh_token = await refresh_tokens(
            db, refresh_token_value, settings
        )
    except AuthError as exc:
        _clear_refresh_cookie(response, settings)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    _set_refresh_cookie(
        response, new_refresh_token, refresh_response.refresh_token_expires_at, settings
    )
    return refresh_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_auth_session(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """revoke the refresh token and clear the cookie"""
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token_value:
        await logout(db, refresh_token_value)
    _clear_refresh_cookie(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
