# reservations api routes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.db.models import User
from app.modules.reservations import (
    cancel_reservation,
    cancel_wish_reservation_as_owner,
    create_reservation,
    get_wish_reservation_status,
    list_my_booked_wishes,
)
from app.modules.reservations.schemas import (
    BookedWishListResponse,
    ReservationResponse,
    WishReservationStatusResponse,
)

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
    redis: Annotated[Redis, Depends(get_redis)],
    share_token: Annotated[str | None, Query()] = None,
) -> ReservationResponse:
    """create reservation for a wish"""
    return await create_reservation(db, current_user, wish_id, share_token=share_token, redis=redis)


@router.delete("/reservations/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    reservation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """cancel own reservation"""
    await cancel_reservation(db, current_user, reservation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/wishes/{wish_id}/reservation", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wish_reservation_as_owner(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """wish owner removes any active reservation on their wish"""
    await cancel_wish_reservation_as_owner(db, current_user, wish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/wishes/{wish_id}/reservation-status", response_model=WishReservationStatusResponse)
async def get_reservation_status(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    share_token: Annotated[str | None, Query()] = None,
) -> WishReservationStatusResponse:
    """get viewer-safe reservation status"""
    return await get_wish_reservation_status(db, current_user, wish_id, share_token=share_token, redis=redis)


@router.get("/me/booked-wishes", response_model=BookedWishListResponse)
async def get_my_booked_wishes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> BookedWishListResponse:
    """list wishes the current user has actively booked"""
    return await list_my_booked_wishes(db, current_user)
