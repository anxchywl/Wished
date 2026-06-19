"""user schemas"""
from datetime import date
from datetime import datetime

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    """user profile response"""
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    birthday: date | None = None
    is_self: bool = False
    is_following: bool = False


class FollowedUserResponse(UserProfileResponse):
    """followed user response"""
    followed_at: datetime


class FollowedUserListResponse(BaseModel):
    """followed user list response"""
    items: list[FollowedUserResponse]
