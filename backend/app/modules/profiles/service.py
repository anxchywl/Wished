from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.modules.profiles.schemas import (
    PrivacySettingsResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.modules.users.service import build_public_profile_url, build_telegram_startapp_url


def _supported_wishlist_visibility(value: str) -> str:
    if value in ("private", "public"):
        return value
    return "public"


def build_profile_response(user: User) -> ProfileResponse:
    """build profile response"""
    return ProfileResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        public_username=getattr(user, "public_username", None),
        public_profile_url=build_public_profile_url(user),
        telegram_startapp_url=build_telegram_startapp_url(user),
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        language_code=user.language_code,
        is_premium=user.is_premium,
        birthday=user.birthday,
        privacy=PrivacySettingsResponse(
            profile_visibility=user.profile_visibility,
            birthday_visibility=user.birthday_visibility,
            wishlist_visibility=_supported_wishlist_visibility(user.wishlist_visibility),
            booking_visibility=user.booking_visibility,
            group_gift_visibility=user.group_gift_visibility,
        ),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


async def update_current_profile(
    db: AsyncSession,
    user: User,
    payload: ProfileUpdateRequest,
) -> ProfileResponse:
    """update current profile"""
    update_data = payload.model_dump(exclude_unset=True)

    if "birthday" in update_data:
        user.birthday = payload.birthday

    if payload.privacy is not None:
        privacy_data = payload.privacy.model_dump(exclude_unset=True)
        if "profile_visibility" in privacy_data:
            user.profile_visibility = payload.privacy.profile_visibility
        if "birthday_visibility" in privacy_data:
            user.birthday_visibility = payload.privacy.birthday_visibility
        if "wishlist_visibility" in privacy_data:
            user.wishlist_visibility = payload.privacy.wishlist_visibility
        if "booking_visibility" in privacy_data:
            user.booking_visibility = payload.privacy.booking_visibility
        if "group_gift_visibility" in privacy_data:
            user.group_gift_visibility = payload.privacy.group_gift_visibility

    await db.commit()
    await db.refresh(user)

    return build_profile_response(user)
