from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db_session
from app.core.config import Settings, get_settings
from app.integrations.telegram import TelegramInitDataError, validate_telegram_init_data
from app.modules.auth import AuthError, authenticate_telegram_user, logout, refresh_tokens
from app.modules.auth.schemas import (
    LogoutRequest,
    RefreshResponse,
    RefreshTokenRequest,
    TelegramAuthRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    payload: TelegramAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """authenticate telegram user"""
    try:
        telegram_user = validate_telegram_init_data(
            init_data=payload.init_data,
            bot_token=settings.telegram_bot_token,
            max_age_seconds=settings.telegram_init_data_max_age_seconds,
        )
    except TelegramInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication data",
        ) from exc

    return await authenticate_telegram_user(db, telegram_user, settings)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_auth_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RefreshResponse:
    """refresh auth tokens"""
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
