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
from app.modules.auth.rate_limit import check_auth_rate_limit
from app.modules.auth.schemas import (
    LogoutRequest,
    RefreshResponse,
    RefreshTokenRequest,
    TelegramAuthRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    request: Request,
    payload: TelegramAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenResponse:
    """authenticate telegram user"""
    await check_auth_rate_limit(redis, request)
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

    return await authenticate_telegram_user(db, telegram_user, settings)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_auth_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> RefreshResponse:
    """refresh auth tokens"""
    await check_auth_rate_limit(redis, request)
    try:
        return await refresh_tokens(db, payload.refresh_token, settings)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_auth_session(
    payload: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """logout auth session"""
    await logout(db, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
