from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProfileVisibility = Literal["private", "public", "friends"]
BirthdayVisibility = Literal["private", "public", "friends", "hidden"]
WishlistVisibility = Literal["private", "public", "friends"]


class PrivacySettingsResponse(BaseModel):
    """privacy settings response"""
    profile_visibility: ProfileVisibility
    birthday_visibility: BirthdayVisibility
    wishlist_visibility: WishlistVisibility


class ProfileResponse(BaseModel):
    """profile response"""
    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    language_code: str | None
    is_premium: bool | None
    birthday: date | None
    privacy: PrivacySettingsResponse
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class PrivacySettingsUpdate(BaseModel):
    """privacy settings update"""
    model_config = ConfigDict(extra="forbid")

    profile_visibility: ProfileVisibility | None = None
    birthday_visibility: BirthdayVisibility | None = None
    wishlist_visibility: WishlistVisibility | None = None


class ProfileUpdateRequest(BaseModel):
    """profile update request"""
    model_config = ConfigDict(extra="forbid")

    birthday: date | None = Field(default=None)
    privacy: PrivacySettingsUpdate | None = None

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date | None) -> date | None:
        """validate birthday"""
        if value is None:
            return value
        if value > date.today():
            raise ValueError("Birthday must not be in the future")
        if value < date(1900, 1, 1):
            raise ValueError("Birthday must not be earlier than 1900-01-01")
        return value
