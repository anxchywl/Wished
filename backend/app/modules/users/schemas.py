"""user schemas"""
from datetime import date
from uuid import UUID

from pydantic import BaseModel


class UserSearchResponse(BaseModel):
    """user search response"""
    id: UUID
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    birthday: date | None = None


class UserProfileResponse(BaseModel):
    """user profile response"""
    id: UUID
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    birthday: date | None = None
