from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    """telegram auth request"""
    init_data: str = Field(min_length=1)



class UserResponse(BaseModel):
    """auth user response"""
    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    language_code: str | None
    is_premium: bool | None


class TokenResponse(BaseModel):
    """token response — refresh token is delivered as an httpOnly cookie"""
    access_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    user: UserResponse


class RefreshResponse(BaseModel):
    """refresh response — new refresh token is delivered as an httpOnly cookie"""
    access_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
