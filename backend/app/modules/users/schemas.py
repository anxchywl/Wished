"""user schemas"""

from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    """user profile response"""

    user_id: str
    username: str | None
    public_username: str | None = None
    public_profile_url: str | None = None
    telegram_startapp_url: str | None = None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    birthday: date | None = None
    is_self: bool = False
    is_following: bool = False


class FollowedUserResponse(UserProfileResponse):
    """followed user response"""

    followed_at: datetime
    position: int


class FollowedUserListResponse(BaseModel):
    """followed user list response"""

    items: list[FollowedUserResponse]


class FollowedUserReorderRequest(BaseModel):
    """followed user reorder request"""

    user_ids: list[UUID]
