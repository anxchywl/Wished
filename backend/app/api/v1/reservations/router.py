# reservations api routes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.db.models import User
from app.modules.reservations import (
    cancel_reservation,
    create_reservation,
    get_wish_reservation_status,
)
from app.modules.reservations.schemas import ReservationResponse, WishReservationStatusResponse

router = APIRouter(tags=["reservations"])


@router.post(
    "/wishes/{wish_id}/reserve",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_reservation(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReservationResponse:
    """create reservation for a wish"""
    return await create_reservation(db, current_user, wish_id)


@router.delete("/reservations/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    reservation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """cancel reservation"""
    await cancel_reservation(db, current_user, reservation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/wishes/{wish_id}/reservation-status", response_model=WishReservationStatusResponse)
async def get_reservation_status(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WishReservationStatusResponse:
    """get viewer-safe reservation status"""
    return await get_wish_reservation_status(db, current_user, wish_id)
