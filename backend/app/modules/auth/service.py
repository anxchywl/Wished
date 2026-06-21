from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security.jwt import create_access_token
from app.core.security.tokens import generate_refresh_token, hash_token
from app.db.models import RefreshToken, User
from app.integrations.telegram import TelegramUserData
from app.modules.auth.schemas import RefreshResponse, TokenResponse, UserResponse


class AuthError(Exception):
    """authentication error"""
    pass


async def authenticate_telegram_user(
    db: AsyncSession,
    telegram_user: TelegramUserData,
    settings: Settings,
) -> tuple[TokenResponse, str]:
    """authenticate telegram user; returns (response, refresh_token_plaintext)"""
    user = await _get_or_create_user(db, telegram_user)
    _update_user_from_telegram(user, telegram_user)
    user.last_login_at = datetime.now(UTC)

    access_token, access_expires_at = create_access_token(user.id, settings)
    refresh_token_value, refresh_token, refresh_expires_at = _create_refresh_token(user.id, settings)
    db.add(refresh_token)

    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=access_token,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        user=_to_user_response(user),
    ), refresh_token_value


async def refresh_tokens(
    db: AsyncSession,
    refresh_token_value: str,
    settings: Settings,
) -> tuple[RefreshResponse, str]:
    """rotate refresh token; returns (response, new_refresh_token_plaintext)"""
    existing_token = await _get_active_refresh_token(db, refresh_token_value)
    existing_token.revoked_at = datetime.now(UTC)

    access_token, access_expires_at = create_access_token(existing_token.user_id, settings)
    new_refresh_token_value, new_refresh_token, refresh_expires_at = _create_refresh_token(
        existing_token.user_id,
        settings,
    )
    db.add(new_refresh_token)

    await db.commit()

    return RefreshResponse(
        access_token=access_token,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
    ), new_refresh_token_value


async def logout(db: AsyncSession, refresh_token_value: str) -> None:
    """revoke refresh token"""
    token_hash = hash_token(refresh_token_value)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    refresh_token = result.scalar_one_or_none()

    if refresh_token and refresh_token.revoked_at is None:
        refresh_token.revoked_at = datetime.now(UTC)
        await db.commit()


async def _get_or_create_user(db: AsyncSession, telegram_user: TelegramUserData) -> User:
    """get or create user"""
    await db.execute(
        postgres_insert(User)
        .values(telegram_id=telegram_user.telegram_id)
        .on_conflict_do_nothing(index_elements=[User.__table__.c.telegram_id])
    )

    result = await db.execute(select(User).where(User.telegram_id == telegram_user.telegram_id))
    user = result.scalar_one()
    return user


def _update_user_from_telegram(user: User, telegram_user: TelegramUserData) -> None:
    """sync telegram fields on every login so photo_url stays fresh"""
    user.username = telegram_user.username
    user.first_name = telegram_user.first_name
    user.last_name = telegram_user.last_name
    if telegram_user.photo_url is not None:
        user.photo_url = telegram_user.photo_url
    # preserve explicit language choice; only seed on first login
    if user.language_code is None:
        user.language_code = telegram_user.language_code
    user.is_premium = telegram_user.is_premium


async def _get_active_refresh_token(db: AsyncSession, refresh_token_value: str) -> RefreshToken:
    """find active refresh token"""
    token_hash = hash_token(refresh_token_value)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    refresh_token = result.scalar_one_or_none()

    if not refresh_token:
        raise AuthError("Invalid refresh token")
    if refresh_token.revoked_at is not None:
        raise AuthError("Refresh token has been revoked")
    if refresh_token.expires_at <= datetime.now(UTC):
        raise AuthError("Refresh token has expired")

    return refresh_token


def _create_refresh_token(user_id: UUID, settings: Settings) -> tuple[str, RefreshToken, datetime]:
    """create refresh token"""
    plaintext_token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(plaintext_token),
        expires_at=expires_at,
    )
    return plaintext_token, refresh_token, expires_at


def _to_user_response(user: User) -> UserResponse:
    """build user response"""
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        language_code=user.language_code,
        is_premium=user.is_premium,
    )
