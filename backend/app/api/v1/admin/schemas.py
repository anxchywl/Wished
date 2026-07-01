from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AdminStatsResponse(BaseModel):
    """dashboard aggregate counts"""

    total_users: int
    active_users: int
    total_wishlists: int
    total_wishes: int
    active_wishes: int
    total_reservations: int
    total_media: int
    total_follows: int


class AdminUserItem(BaseModel):
    """admin view of a user record"""

    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    created_at: str
    last_login_at: str | None
    wishlist_count: int
    wish_count: int
    is_blocked: bool
    blocked_at: str | None
    blocked_reason: str | None
    is_admin: bool


class AdminWishlistItem(BaseModel):
    """admin view of a wishlist"""

    id: UUID
    owner_telegram_id: int
    owner_username: str | None
    title: str
    visibility: str
    wish_count: int
    created_at: str


class AdminWishItem(BaseModel):
    """admin view of a wish"""

    id: UUID
    wishlist_id: UUID
    owner_telegram_id: int
    owner_username: str | None
    title: str
    status: str
    created_at: str
    has_reservation: bool
    image_count: int


class AdminMediaItem(BaseModel):
    """admin view of a media record"""

    id: UUID
    wish_id: UUID
    owner_telegram_id: int
    object_name: str
    status: str
    created_at: str


class AuditLogItem(BaseModel):
    """admin audit log entry"""

    id: int
    actor_user_id: UUID | None
    actor_telegram_id: int | None
    action: str
    target_type: str | None
    target_id: str | None
    metadata_json: Any | None
    created_at: str


class BlockUserRequest(BaseModel):
    """payload for block action"""

    reason: str


class ModerationLogItem(BaseModel):
    """one entry in a user's moderation history"""

    id: UUID
    user_id: UUID
    action: str
    reason: str | None
    performed_by: UUID
    created_at: str


class AdminMeResponse(BaseModel):
    """confirms admin identity"""

    is_admin: bool
    telegram_id: int
