# reservations business logic service
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Reservation, User, Wish, Wishlist
from app.db.models.group_gifts import GroupGift
from app.modules.wishlists.share_token import validate_wishlist_share_token
from app.modules.reservations.schemas import (
    BookedWishItem,
    BookedWishListResponse,
    ReservationResponse,
    WishReservationStatusResponse,
)


async def create_reservation(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    share_token: str | None = None,
    redis: Redis | None = None,
) -> ReservationResponse:
    """create reservation for a wish — owner may reserve their own wish"""
    await _get_accessible_wish(db, current_user, wish_id, share_token=share_token, redis=redis)

    result = await db.execute(
        select(GroupGift).where(
            GroupGift.wish_id == wish_id,
            GroupGift.status == "active",
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This wish has an active group gift",
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


async def cancel_wish_reservation_as_owner(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
) -> None:
    """wish owner removes any active reservation on their wish"""
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.wishlist))
        .where(Wish.id == wish_id)
    )
    wish = result.scalar_one_or_none()
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if wish.wishlist.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the wish owner")

    result = await db.execute(
        select(Reservation).where(
            Reservation.wish_id == wish_id,
            Reservation.status == "active",
        )
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active reservation on this wish",
        )

    reservation.status = "cancelled"
    await db.commit()


async def get_wish_reservation_status(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    share_token: str | None = None,
    redis: Redis | None = None,
) -> WishReservationStatusResponse:
    """return viewer-safe reservation status, respecting the wish owner's booking_visibility setting"""
    wish = await _get_accessible_wish(db, current_user, wish_id, require_active=False, share_token=share_token, redis=redis)
    is_owner = wish.wishlist.owner_user_id == current_user.id

    gift_count = await db.scalar(
        select(func.count()).select_from(GroupGift).where(
            GroupGift.wish_id == wish_id,
            GroupGift.status == "active",
        )
    )
    has_active_group_gift = (gift_count or 0) > 0

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
            owner_booking_visibility=current_user.booking_visibility if is_owner else None,
            has_active_group_gift=has_active_group_gift,
        )

    is_mine = reservation.reserver_user_id == current_user.id

    if is_owner and not is_mine:
        visibility = current_user.booking_visibility
        reserver_display_name = None
        if visibility == "names":
            reserver = await db.get(User, reservation.reserver_user_id)
            if reserver is not None:
                reserver_display_name = (
                    f"@{reserver.username}"
                    if reserver.username
                    else reserver.first_name
                )
        return WishReservationStatusResponse(
            wish_id=wish_id,
            is_reserved=True,
            is_mine=False,
            reservation_id=None,
            owner_booking_visibility=visibility,
            reserver_display_name=reserver_display_name,
            has_active_group_gift=has_active_group_gift,
        )

    return WishReservationStatusResponse(
        wish_id=wish_id,
        is_reserved=True,
        is_mine=is_mine,
        # only expose reservation id to the reserver
        reservation_id=reservation.id if is_mine else None,
        has_active_group_gift=has_active_group_gift,
    )


async def list_my_booked_wishes(
    db: AsyncSession,
    current_user: User,
) -> BookedWishListResponse:
    """list wishes the current user has actively booked (reserved)"""
    result = await db.execute(
        select(Reservation)
        .join(Wish, Wish.id == Reservation.wish_id)
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .options(
            selectinload(Reservation.wish).options(
                selectinload(Wish.images),
                selectinload(Wish.wishlist).options(selectinload(Wishlist.owner)),
            )
        )
        .where(
            Reservation.reserver_user_id == current_user.id,
            Reservation.status == "active",
            Wishlist.owner_user_id != current_user.id,
        )
        .order_by(Reservation.created_at.desc())
    )
    reservations = result.scalars().all()

    from app.integrations.minio import get_presigned_url
    from app.modules.media.schemas import WishImageResponse

    items = []
    for rsv in reservations:
        wish = rsv.wish
        wishlist = wish.wishlist
        owner = wishlist.owner
        images = [
            WishImageResponse(
                id=img.id,
                wish_id=img.wish_id,
                url=get_presigned_url(img.bucket, img.object_name),
                thumbnail_url=(
                    get_presigned_url(img.bucket, img.thumbnail_object_name)
                    if img.thumbnail_object_name else None
                ),
                medium_url=(
                    get_presigned_url(img.bucket, img.medium_object_name)
                    if img.medium_object_name else None
                ),
                file_name=img.file_name,
                content_type=img.content_type,
                size_bytes=img.size_bytes,
                status=img.status,
                created_at=img.created_at,
            )
            for img in wish.images
        ]
        items.append(
            BookedWishItem(
                reservation_id=rsv.id,
                wish_id=wish.id,
                wish_title=wish.title,
                wish_description=wish.description,
                wish_url=wish.url,
                wish_price=str(wish.price) if wish.price is not None else None,
                wish_currency=wish.currency,
                wish_status=wish.status,
                wishlist_id=wishlist.id,
                wishlist_title=wishlist.title,
                owner_first_name=owner.first_name,
                owner_username=owner.username,
                owner_photo_url=owner.photo_url,
                images=images,
                reserved_at=rsv.created_at,
            )
        )

    return BookedWishListResponse(items=items)


async def _get_accessible_wish(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    require_active: bool = True,
    share_token: str | None = None,
    redis: Redis | None = None,
) -> Wish:
    """find wish accessible to the user; share_token grants access to private wishlists"""
    result = await db.execute(
        select(Wish)
        .options(selectinload(Wish.wishlist))
        .where(Wish.id == wish_id)
    )
    wish = result.scalar_one_or_none()
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if wish.wishlist.owner_user_id != current_user.id and wish.wishlist.visibility != "public":
        if share_token and redis:
            if await validate_wishlist_share_token(redis, share_token, wish.wishlist_id):
                if require_active and wish.status != "active":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Wish is not available for reservation",
                    )
                return wish
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if require_active and wish.status != "active":
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
