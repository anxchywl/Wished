# reservations pydantic schemas
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.media.schemas import WishImageResponse


class ReservationResponse(BaseModel):
    """reservation response for the reserver"""
    id: UUID
    wish_id: UUID
    reserver_user_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class WishReservationStatusResponse(BaseModel):
    """viewer-safe reservation status — never leaks reserver identity to owner"""
    wish_id: UUID
    is_reserved: bool
    is_mine: bool
    reservation_id: UUID | None
    owner_booking_visibility: str | None = None
    reserver_display_name: str | None = None


class BookedWishItem(BaseModel):
    """single wish the current user has booked"""
    reservation_id: UUID
    wish_id: UUID
    wish_title: str
    wish_description: str | None
    wish_url: str | None
    wish_price: str | None
    wish_currency: str | None
    wish_status: str
    wishlist_id: UUID
    wishlist_title: str
    owner_first_name: str | None
    owner_username: str | None
    owner_photo_url: str | None
    images: list[WishImageResponse]
    reserved_at: datetime


class BookedWishListResponse(BaseModel):
    """list of wishes the current user has booked"""
    items: list[BookedWishItem]
