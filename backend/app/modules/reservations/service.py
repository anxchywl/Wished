# reservations business logic service
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Reservation, User, Wish, Wishlist
from app.modules.reservations.schemas import ReservationResponse, WishReservationStatusResponse


async def create_reservation(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
) -> ReservationResponse:
    """create reservation for a wish"""
    wish = await _get_accessible_wish(db, current_user, wish_id)

    if wish.wishlist.owner_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot reserve your own wish",
        )

    # check for existing active reservation inside a transaction
    result = await db.execute(
        select(Reservation).where(
            Reservation.wish_id == wish_id,
            Reservation.status == "active",
        ).with_for_update()
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.reserver_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already reserved",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is already reserved",
        )

    reservation = Reservation(
        wish_id=wish_id,
        reserver_user_id=current_user.id,
        status="active",
    )
    db.add(reservation)
    try:
        await db.commit()
    except IntegrityError:
        # two concurrent requests raced through the for-update check;
        # the partial unique index uq_reservations_wish_active rejected the loser
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is already reserved",
        )
    await db.refresh(reservation)
    return _to_response(reservation)


async def cancel_reservation(
    db: AsyncSession,
    current_user: User,
    reservation_id: UUID,
) -> None:
    """cancel own reservation"""
    result = await db.execute(
        select(Reservation).where(
            Reservation.id == reservation_id,
            Reservation.reserver_user_id == current_user.id,
        )
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    if reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is not active",
        )

    reservation.status = "cancelled"
    await db.commit()


async def get_wish_reservation_status(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
) -> WishReservationStatusResponse:
    """return viewer-safe reservation status"""
    # verify the wish exists and is accessible
    await _get_accessible_wish(db, current_user, wish_id)

    result = await db.execute(
        select(Reservation).where(
            Reservation.wish_id == wish_id,
            Reservation.status == "active",
        )
    )
    reservation = result.scalar_one_or_none()

    if not reservation:
        return WishReservationStatusResponse(
            wish_id=wish_id,
            is_reserved=False,
            is_mine=False,
            reservation_id=None,
        )

    is_mine = reservation.reserver_user_id == current_user.id
    return WishReservationStatusResponse(
        wish_id=wish_id,
        is_reserved=True,
        is_mine=is_mine,
        # only expose reservation id to the reserver, not to random viewers
        reservation_id=reservation.id if is_mine else None,
    )


async def _get_accessible_wish(db: AsyncSession, current_user: User, wish_id: UUID) -> Wish:
    """find wish accessible to the user — only returns active wishes for reservation purposes"""
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.wishlist))
        .where(Wish.id == wish_id)
    )
    wish = result.scalar_one_or_none()
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if wish.wishlist.owner_user_id != current_user.id and wish.wishlist.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is not available for reservation",
        )
    return wish


def _to_response(reservation: Reservation) -> ReservationResponse:
    """build reservation response"""
    return ReservationResponse(
        id=reservation.id,
        wish_id=reservation.wish_id,
        reserver_user_id=reservation.reserver_user_id,
        status=reservation.status,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
    )
