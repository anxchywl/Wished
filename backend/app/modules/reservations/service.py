# reservations business logic service
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Reservation, User, Wish, Wishlist
from app.db.models.group_gifts import GroupGift, GroupGiftContribution
from app.modules.wishlists.share_token import validate_wishlist_share_token
from app.modules.reservations.schemas import (
    BookedWishContributorSummary,
    BookedWishGroupGiftDetail,
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
    active_gift_exists = (gift_count or 0) > 0

    # load owner once; used for visibility checks and group_gift_visibility throughout
    wish_owner: User | None = None
    if not is_owner:
        wish_owner = await db.get(User, wish.wishlist.owner_user_id)
    owner_gg_visibility: str = (
        getattr(wish_owner, "group_gift_visibility", "hide")
        if wish_owner else
        getattr(current_user, "group_gift_visibility", "hide")
    )

    has_active_group_gift = active_gift_exists

    result = await db.execute(
        select(Reservation).where(
            Reservation.wish_id == wish_id,
            Reservation.status == "active",
        )
    )
    reservation = result.scalar_one_or_none()

    if not reservation:
        if is_owner:
            return WishReservationStatusResponse(
                wish_id=wish_id,
                is_reserved=False,
                is_mine=False,
                reservation_id=None,
                owner_booking_visibility=current_user.booking_visibility,
                owner_group_gift_visibility=getattr(current_user, "group_gift_visibility", "hide"),
                has_active_group_gift=has_active_group_gift,
            )
        return WishReservationStatusResponse(
            wish_id=wish_id,
            is_reserved=False,
            is_mine=False,
            reservation_id=None,
            owner_group_gift_visibility=owner_gg_visibility,
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
            owner_group_gift_visibility=getattr(current_user, "group_gift_visibility", "hide"),
            reserver_display_name=reserver_display_name,
            has_active_group_gift=has_active_group_gift,
        )

    return WishReservationStatusResponse(
        wish_id=wish_id,
        is_reserved=True,
        is_mine=is_mine,
        # only expose reservation id to the reserver
        reservation_id=reservation.id if is_mine else None,
        owner_group_gift_visibility=owner_gg_visibility if not is_owner else None,
        has_active_group_gift=has_active_group_gift,
    )


async def list_my_booked_wishes(
    db: AsyncSession,
    current_user: User,
) -> BookedWishListResponse:
    """list wishes the current user has actively booked (reserved or group-gifted)"""
    from app.integrations.minio import get_presigned_url
    from app.modules.media.schemas import WishImageResponse

    # regular reservations (non-group-gift)
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

    # completed group gifts where user is organizer or contributor
    gift_result = await db.execute(
        select(GroupGift)
        .join(Wish, Wish.id == GroupGift.wish_id)
        .join(Wishlist, Wishlist.id == Wish.wishlist_id)
        .options(
            selectinload(GroupGift.wish).options(
                selectinload(Wish.images),
                selectinload(Wish.wishlist).options(selectinload(Wishlist.owner)),
            ),
            selectinload(GroupGift.organizer),
            selectinload(GroupGift.contributions).selectinload(GroupGiftContribution.contributor),
            selectinload(GroupGift.approvals),
        )
        .where(
            GroupGift.status.in_(["active", "completed"]),
            Wishlist.owner_user_id != current_user.id,
        )
    )
    completed_gifts = gift_result.scalars().all()

    # filter to gifts where user is organizer or active contributor
    my_gifts: list[GroupGift] = []
    for gift in completed_gifts:
        non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
        is_organizer = gift.organizer_user_id == current_user.id
        is_contributor = any(c.contributor_user_id == current_user.id for c in non_cancelled)
        if is_organizer or is_contributor:
            my_gifts.append(gift)

    # build set of wish_ids covered by group gifts to avoid duplicates in reservation list
    gift_wish_ids = {g.wish_id for g in my_gifts}

    def _make_images(wish: Wish) -> list[WishImageResponse]:
        return [
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

    items: list[BookedWishItem] = []

    for rsv in reservations:
        wish = rsv.wish
        # skip if this wish is covered as a group gift
        if wish.id in gift_wish_ids:
            continue
        wishlist = wish.wishlist
        owner = wishlist.owner
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
                images=_make_images(wish),
                reserved_at=rsv.created_at,
                is_group_gift=False,
                group_gift=None,
            )
        )

    for gift in my_gifts:
        wish = gift.wish
        wishlist = wish.wishlist
        owner = wishlist.owner
        non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
        is_organizer = gift.organizer_user_id == current_user.id

        cancel_approvals = [a for a in gift.approvals if a.approval_type == "cancel"]
        unbook_approvals = [a for a in gift.approvals if a.approval_type == "unbook"]
        participant_count = 1 + len(non_cancelled)

        from decimal import Decimal as D
        _CONFIRMED = {"confirmed", "pledged", "notified"}
        collected = sum((c.amount for c in non_cancelled if c.status in _CONFIRMED), D("0"))

        organizer = gift.organizer
        contributors = [
            BookedWishContributorSummary(
                first_name=c.contributor.first_name if c.contributor else None,
                username=c.contributor.username if c.contributor else None,
                amount=str(c.amount) if is_organizer else None,
                status=c.status,
            )
            for c in non_cancelled
        ]

        gift_detail = BookedWishGroupGiftDetail(
            group_gift_id=gift.id,
            status=gift.status,
            organizer_first_name=organizer.first_name if organizer else None,
            organizer_username=organizer.username if organizer else None,
            collected_amount=str(collected),
            total_amount=str(wish.price) if wish.price is not None else None,
            percent_complete=(
                min(100, int(collected / wish.price * 100))
                if wish.price and wish.price > 0 else 0
            ),
            participant_count=participant_count,
            cancel_approval_count=len(cancel_approvals),
            unbook_approval_count=len(unbook_approvals),
            my_cancel_approval=any(a.user_id == current_user.id for a in cancel_approvals),
            my_unbook_approval=any(a.user_id == current_user.id for a in unbook_approvals),
            contributors=contributors,
        )

        # find reservation for organizer (contributors share the organizer's reservation)
        rsv_result = await db.execute(
            select(Reservation).where(
                Reservation.wish_id == wish.id,
                Reservation.status == "active",
            )
        )
        organizer_rsv = rsv_result.scalar_one_or_none()

        items.append(
            BookedWishItem(
                reservation_id=organizer_rsv.id if organizer_rsv else None,
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
                images=_make_images(wish),
                reserved_at=gift.created_at,
                is_group_gift=True,
                group_gift=gift_detail,
            )
        )

    items.sort(key=lambda x: x.reserved_at, reverse=True)
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
