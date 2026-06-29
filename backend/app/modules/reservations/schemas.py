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
    owner_group_gift_visibility: str | None = None
    reserver_display_name: str | None = None
    group_gift_organizer_display_name: str | None = None
    has_active_group_gift: bool = False


class BookedWishGroupGiftDetail(BaseModel):
    """group gift details shown to organizer and contributors on booked wish"""

    group_gift_id: UUID
    status: str
    organizer_first_name: str | None
    organizer_username: str | None
    collected_amount: str
    total_amount: str | None
    percent_complete: int
    participant_count: int
    cancel_approval_count: int
    unbook_approval_count: int
    my_cancel_approval: bool
    my_unbook_approval: bool
    contributors: list["BookedWishContributorSummary"]


class BookedWishContributorSummary(BaseModel):
    first_name: str | None
    username: str | None
    amount: str | None
    status: str


class BookedWishItem(BaseModel):
    """single wish the current user has booked"""

    reservation_id: UUID | None
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
    is_group_gift: bool = False
    group_gift: BookedWishGroupGiftDetail | None = None
    position: int


class FulfilledWishItem(BaseModel):
    """single wish the current user helped fulfill"""

    fulfilled_id: UUID
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
    fulfilled_at: datetime
    source: str
    organizer_first_name: str | None = None
    organizer_username: str | None = None
    contributor_count: int | None = None
    user_contribution_amount: str | None = None
    total_collected_amount: str | None = None
    group_gift_id: UUID | None = None
    position: int


class BookedWishListResponse(BaseModel):
    """discover contribution sections for the current user"""

    items: list[BookedWishItem]
    fulfilled_items: list[FulfilledWishItem] = []


class BookedWishReorderRequest(BaseModel):
    """booked wish reorder request"""

    wish_ids: list[UUID]


class FulfilledWishReorderRequest(BaseModel):
    """fulfilled wish reorder request"""

    fulfilled_ids: list[UUID]
