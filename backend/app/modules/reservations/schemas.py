# reservations pydantic schemas
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
