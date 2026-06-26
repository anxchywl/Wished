from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Reservation, User, Wish
from app.db.models.group_gifts import GroupGift, GroupGiftContribution
from app.modules.cache import cache_delete, wishes_cache_key
from app.modules.events import publish_event
from app.modules.group_gifts.schemas import (
    ContributionCreateRequest,
    ContributionSummary,
    GroupGiftCreateRequest,
    GroupGiftMemberSummary,
    GroupGiftPaymentDetailsUpdate,
    GroupGiftResponse,
)

_CONFIRMED_STATUSES = {"confirmed", "pledged", "notified"}
_TERMINAL_STATUSES = {"confirmed", "notified"}


def _organizer_display_name(organizer: User | None) -> str | None:
    if organizer is None:
        return None
    return f"@{organizer.username}" if organizer.username else organizer.first_name


def _sum_committed(contributions: list[GroupGiftContribution]) -> Decimal:
    return sum(
        (c.amount for c in contributions if c.status != "cancelled"),
        Decimal("0"),
    )


def _build_group_gift_response(
    wish: Wish,
    gift: GroupGift,
    current_user: User,
    non_cancelled: list[GroupGiftContribution],
    status_override: str | None = None,
) -> GroupGiftResponse:
    raw_collected_amount = sum(
        (c.amount for c in non_cancelled if c.status in _CONFIRMED_STATUSES),
        Decimal("0"),
    )
    committed_amount = _sum_committed(non_cancelled)
    total_amount = wish.price
    collected_amount = (
        min(raw_collected_amount, total_amount)
        if total_amount and total_amount > 0
        else raw_collected_amount
    )
    remaining_amount = (
        max(total_amount - committed_amount, Decimal("0"))
        if total_amount and total_amount > 0
        else None
    )
    percent_complete = (
        min(100, int(collected_amount / total_amount * 100))
        if total_amount and total_amount > 0
        else 0
    )

    is_organizer = current_user.id == gift.organizer_user_id
    my_contrib = next(
        (c for c in non_cancelled if c.contributor_user_id == current_user.id),
        None,
    )
    is_contributor = my_contrib is not None
    display_status = status_override or (
        "cancelled" if gift.organizer and gift.organizer.is_blocked else gift.status
    )

    show_payment = display_status != "cancelled" and (is_organizer or is_contributor)
    organizer_display_name: str | None = None
    if is_contributor and my_contrib.status in _CONFIRMED_STATUSES:
        organizer_display_name = _organizer_display_name(gift.organizer)

    is_owner = wish.wishlist.owner_user_id == current_user.id
    if is_owner and not is_organizer and not is_contributor:
        visibility = getattr(current_user, "group_gift_visibility", "hide")
        if visibility == "names":
            organizer_display_name = _organizer_display_name(gift.organizer)
        else:
            organizer_display_name = None
        show_payment = False

    if display_status == "cancelled":
        show_payment = False

    return GroupGiftResponse(
        id=gift.id,
        wish_id=gift.wish_id,
        collection_type=gift.collection_type,
        status=display_status,
        payment_method=gift.payment_method if show_payment else None,
        payment_phone=gift.payment_phone if show_payment else None,
        payment_comment=gift.payment_comment if show_payment else None,
        total_amount=total_amount,
        collected_amount=collected_amount,
        remaining_amount=remaining_amount,
        percent_complete=percent_complete,
        contributor_count=len(non_cancelled),
        is_organizer=is_organizer,
        is_contributor=is_contributor,
        my_contribution=(
            ContributionSummary(
                id=my_contrib.id,
                amount=my_contrib.amount,
                status=my_contrib.status,
                created_at=my_contrib.created_at,
            )
            if my_contrib
            else None
        ),
        organizer_display_name=organizer_display_name,
        created_at=gift.created_at,
    )


async def create_group_gift(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
    payload: GroupGiftCreateRequest,
    redis: Redis | None = None,
) -> GroupGiftResponse:
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

    if wish.wishlist.owner_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wish owner cannot organize a group gift on their own wish",
        )

    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is not available for a group gift",
        )

    result = await db.execute(
        select(Reservation)
        .where(Reservation.wish_id == wish_id, Reservation.status == "active")
        .with_for_update()
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is already reserved",
        )

    result = await db.execute(
        select(GroupGift)
        .where(GroupGift.wish_id == wish_id, GroupGift.status == "active")
        .with_for_update()
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A group gift already exists for this wish",
        )

    gift = GroupGift(
        wish_id=wish_id,
        organizer_user_id=current_user.id,
        collection_type=payload.collection_type,
        status="active",
        payment_method=payload.payment_method,
        payment_phone=payload.payment_phone,
        payment_comment=payload.payment_comment,
    )
    db.add(gift)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A group gift already exists for this wish",
        )
    await db.refresh(gift)

    if redis:
        await publish_event(redis, "GROUP_GIFT_CREATED", {
            "wish_id": str(wish_id),
            "group_gift_id": str(gift.id),
            "organizer_user_id": str(current_user.id),
            "wish_title": wish.title,
            "wishlist_owner_user_id": str(wish.wishlist.owner_user_id),
        })

    return GroupGiftResponse(
        id=gift.id,
        wish_id=gift.wish_id,
        collection_type=gift.collection_type,
        status=gift.status,
        payment_method=gift.payment_method,
        payment_phone=gift.payment_phone,
        payment_comment=gift.payment_comment,
        total_amount=wish.price,
        collected_amount=Decimal("0"),
        remaining_amount=wish.price,
        percent_complete=0,
        contributor_count=0,
        is_organizer=True,
        is_contributor=False,
        my_contribution=None,
        organizer_display_name=None,
        created_at=gift.created_at,
    )


async def get_group_gift(
    db: AsyncSession,
    current_user: User,
    wish_id: UUID,
) -> GroupGiftResponse | None:
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

    result = await db.execute(
        select(GroupGift)
        .options(selectinload(GroupGift.contributions), selectinload(GroupGift.organizer))
        .where(GroupGift.wish_id == wish_id, GroupGift.status == "active")
    )
    gift = result.scalar_one_or_none()
    if not gift:
        return None

    is_owner = wish.wishlist.owner_user_id == current_user.id
    is_organizer = current_user.id == gift.organizer_user_id
    non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
    is_contributor = any(c.contributor_user_id == current_user.id for c in non_cancelled)
    if is_owner and not is_organizer and not is_contributor:
        visibility = getattr(current_user, "group_gift_visibility", "hide")
        if visibility == "hide":
            return None

    return _build_group_gift_response(wish, gift, current_user, non_cancelled)


async def update_payment_details(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
    payload: GroupGiftPaymentDetailsUpdate,
) -> GroupGiftResponse:
    result = await db.execute(
        select(GroupGift)
        .options(
            selectinload(GroupGift.wish).selectinload(Wish.wishlist),
            selectinload(GroupGift.contributions),
            selectinload(GroupGift.organizer),
        )
        .where(GroupGift.id == group_gift_id)
        .with_for_update()
    )
    gift = result.scalar_one_or_none()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group gift not found")
    if gift.organizer_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")
    if gift.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group gift is not active",
        )

    gift.payment_method = payload.payment_method
    gift.payment_phone = payload.payment_phone
    gift.payment_comment = payload.payment_comment
    await db.commit()
    await db.refresh(gift)

    non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
    return _build_group_gift_response(gift.wish, gift, current_user, non_cancelled)


async def mark_group_gift_purchased(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
    redis: Redis | None = None,
) -> GroupGiftResponse:
    result = await db.execute(
        select(GroupGift)
        .options(
            selectinload(GroupGift.wish).selectinload(Wish.wishlist),
            selectinload(GroupGift.contributions),
            selectinload(GroupGift.organizer),
        )
        .where(GroupGift.id == group_gift_id)
        .with_for_update()
    )
    gift = result.scalar_one_or_none()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group gift not found")
    if gift.organizer_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")
    if gift.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group gift is cancelled",
        )

    wish = gift.wish
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is not active",
        )

    result = await db.execute(
        select(Reservation)
        .where(Reservation.wish_id == wish.id, Reservation.status == "active")
        .with_for_update()
    )
    reservation = result.scalar_one_or_none()
    if reservation and reservation.reserver_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is already reserved",
        )

    if reservation is None:
        reservation = Reservation(
            wish_id=wish.id,
            reserver_user_id=current_user.id,
            status="active",
        )
        db.add(reservation)

    gift.status = "completed"
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wish is already reserved",
        ) from None
    await db.refresh(gift)

    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wish.wishlist_id))

    non_cancelled = [c for c in gift.contributions if c.status != "cancelled"]
    return _build_group_gift_response(
        wish,
        gift,
        current_user,
        non_cancelled,
        status_override="completed",
    )


async def cancel_group_gift(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
    redis: Redis | None = None,
) -> None:
    result = await db.execute(
        select(GroupGift)
        .options(selectinload(GroupGift.wish))
        .where(GroupGift.id == group_gift_id)
    )
    gift = result.scalar_one_or_none()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group gift not found")

    if gift.organizer_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")

    wishlist_id = gift.wish.wishlist_id
    await db.delete(gift)
    await db.commit()

    if redis is not None:
        await cache_delete(redis, wishes_cache_key(wishlist_id))


async def join_group_gift(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
    payload: ContributionCreateRequest,
    redis: Redis | None = None,
) -> ContributionSummary:
    result = await db.execute(
        select(GroupGift)
        .options(selectinload(GroupGift.wish).selectinload(Wish.wishlist))
        .where(GroupGift.id == group_gift_id)
        .with_for_update()
    )
    gift = result.scalar_one_or_none()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group gift not found")

    if gift.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Gift is not active")

    result = await db.execute(
        select(GroupGiftContribution)
        .where(
            GroupGiftContribution.group_gift_id == group_gift_id,
            GroupGiftContribution.contributor_user_id == current_user.id,
            GroupGiftContribution.status != "cancelled",
        )
        .with_for_update()
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already contributing to this gift",
        )

    result = await db.execute(
        select(GroupGiftContribution)
        .where(
            GroupGiftContribution.group_gift_id == group_gift_id,
            GroupGiftContribution.status != "cancelled",
        )
        .with_for_update()
    )
    active_contributions = result.scalars().all()
    total_amount = gift.wish.price
    committed_amount = _sum_committed(active_contributions)
    remaining_amount = (
        max(total_amount - committed_amount, Decimal("0"))
        if total_amount and total_amount > 0
        else None
    )
    if remaining_amount is not None and payload.amount > remaining_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution exceeds remaining amount: {remaining_amount}",
        )

    initial_status = (
        "waiting_transfer" if gift.collection_type == "immediate" else "pledged"
    )
    contrib = GroupGiftContribution(
        group_gift_id=group_gift_id,
        contributor_user_id=current_user.id,
        amount=payload.amount,
        status=initial_status,
    )
    db.add(contrib)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already contributing to this gift",
        )
    await db.refresh(contrib)

    if gift.collection_type == "commit":
        await _maybe_notify_goal_reached(db, gift, redis, committed_before=committed_amount)

    return ContributionSummary(
        id=contrib.id,
        amount=contrib.amount,
        status=contrib.status,
        created_at=contrib.created_at,
    )


async def report_transfer(
    db: AsyncSession,
    current_user: User,
    contribution_id: UUID,
    redis: Redis | None = None,
) -> ContributionSummary:
    result = await db.execute(
        select(GroupGiftContribution).where(GroupGiftContribution.id == contribution_id)
    )
    contrib = result.scalar_one_or_none()
    if not contrib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribution not found")

    if contrib.contributor_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your contribution")

    if contrib.status != "waiting_transfer":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer already reported or not in expected state",
        )

    contrib.status = "waiting_confirmation"
    await db.commit()
    await db.refresh(contrib)

    if redis:
        result = await db.execute(
            select(GroupGift)
            .options(selectinload(GroupGift.wish))
            .where(GroupGift.id == contrib.group_gift_id)
        )
        gift = result.scalar_one_or_none()
        if gift:
            await publish_event(redis, "TRANSFER_REPORTED", {
                "contribution_id": str(contribution_id),
                "group_gift_id": str(contrib.group_gift_id),
                "contributor_user_id": str(current_user.id),
                "contributor_first_name": current_user.first_name or current_user.username or "Someone",
                "amount": str(contrib.amount),
                "currency": gift.wish.currency or "",
                "wish_title": gift.wish.title,
                "organizer_user_id": str(gift.organizer_user_id),
            })

    return ContributionSummary(
        id=contrib.id,
        amount=contrib.amount,
        status=contrib.status,
        created_at=contrib.created_at,
    )


async def confirm_transfer(
    db: AsyncSession,
    current_user: User,
    contribution_id: UUID,
    confirmed: bool,
    redis: Redis | None = None,
) -> ContributionSummary:
    result = await db.execute(
        select(GroupGiftContribution)
        .options(
            selectinload(GroupGiftContribution.group_gift).selectinload(GroupGift.wish).selectinload(Wish.wishlist)
        )
        .where(GroupGiftContribution.id == contribution_id)
    )
    contrib = result.scalar_one_or_none()
    if not contrib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribution not found")

    gift = contrib.group_gift
    if gift.organizer_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")

    if contrib.status != "waiting_confirmation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer is not awaiting confirmation",
        )

    if confirmed:
        collected_before = await _compute_collected(db, gift.id)
        contrib.status = "confirmed"
        await db.commit()
        await db.refresh(contrib)

        collected_amount = await _compute_collected(db, gift.id)
        total_amount = gift.wish.price
        percent_complete = (
            min(100, int(collected_amount / total_amount * 100))
            if total_amount and total_amount > 0
            else 0
        )

        await _maybe_notify_goal_reached(db, gift, redis, committed_before=collected_before)

        if redis:
            await publish_event(redis, "TRANSFER_CONFIRMED", {
                "contribution_id": str(contribution_id),
                "contributor_user_id": str(contrib.contributor_user_id),
                "wish_title": gift.wish.title,
                "wish_id": str(gift.wish_id),
                "wishlist_id": str(gift.wish.wishlist_id),
                "owner_user_id": str(gift.wish.wishlist.owner_user_id),
                "percent_complete": percent_complete,
            })
    else:
        contrib.status = "waiting_transfer"
        await db.commit()
        await db.refresh(contrib)

        if redis:
            await publish_event(redis, "TRANSFER_REJECTED", {
                "contribution_id": str(contribution_id),
                "contributor_user_id": str(contrib.contributor_user_id),
                "wish_title": gift.wish.title,
            })

    return ContributionSummary(
        id=contrib.id,
        amount=contrib.amount,
        status=contrib.status,
        created_at=contrib.created_at,
    )


async def leave_group_gift(
    db: AsyncSession,
    current_user: User,
    contribution_id: UUID,
    redis: Redis | None = None,
) -> None:
    result = await db.execute(
        select(GroupGiftContribution)
        .options(
            selectinload(GroupGiftContribution.group_gift).selectinload(GroupGift.wish)
        )
        .where(GroupGiftContribution.id == contribution_id)
    )
    contrib = result.scalar_one_or_none()
    if not contrib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribution not found")

    if contrib.contributor_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your contribution")

    if contrib.status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot leave after transfer is confirmed",
        )

    contrib.status = "cancelled"
    await db.commit()

    gift = contrib.group_gift
    if gift.status == "completed":
        collected_amount = await _compute_collected(db, gift.id)
        total_amount = gift.wish.price
        if not total_amount or collected_amount < total_amount:
            gift.status = "active"
            result = await db.execute(
                select(GroupGiftContribution).where(
                    GroupGiftContribution.group_gift_id == gift.id,
                    GroupGiftContribution.status == "notified",
                )
            )
            for c in result.scalars().all():
                c.status = "pledged"
            await db.commit()


async def organizer_remove_contribution(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
    contribution_id: UUID,
    redis: Redis | None = None,
) -> None:
    result = await db.execute(
        select(GroupGiftContribution)
        .options(
            selectinload(GroupGiftContribution.group_gift).selectinload(GroupGift.wish)
        )
        .where(
            GroupGiftContribution.id == contribution_id,
            GroupGiftContribution.group_gift_id == group_gift_id,
        )
    )
    contrib = result.scalar_one_or_none()
    if not contrib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribution not found")

    if contrib.group_gift.organizer_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")

    contrib.status = "cancelled"
    await db.commit()

    gift = contrib.group_gift
    collected_amount = await _compute_collected(db, gift.id)
    total_amount = gift.wish.price
    if not total_amount or collected_amount < total_amount:
        if gift.status == "completed":
            gift.status = "active"
        result = await db.execute(
            select(GroupGiftContribution).where(
                GroupGiftContribution.group_gift_id == gift.id,
                GroupGiftContribution.status == "notified",
            )
        )
        for c in result.scalars().all():
            c.status = "pledged"
        await db.commit()

    if redis and gift.wish:
        await cache_delete(redis, wishes_cache_key(gift.wish.wishlist_id))


async def get_gift_members(
    db: AsyncSession,
    current_user: User,
    group_gift_id: UUID,
) -> list[GroupGiftMemberSummary]:
    result = await db.execute(
        select(GroupGift)
        .options(
            selectinload(GroupGift.wish).selectinload(Wish.wishlist),
            selectinload(GroupGift.organizer),
        )
        .where(GroupGift.id == group_gift_id)
    )
    gift = result.scalar_one_or_none()
    if not gift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group gift not found")

    is_organizer = gift.organizer_user_id == current_user.id
    is_owner_with_names = (
        gift.wish is not None
        and gift.wish.wishlist.owner_user_id == current_user.id
        and getattr(current_user, "group_gift_visibility", "hide") == "names"
    )

    result = await db.execute(
        select(GroupGiftContribution)
        .options(selectinload(GroupGiftContribution.contributor))
        .where(
            GroupGiftContribution.group_gift_id == group_gift_id,
            GroupGiftContribution.status != "cancelled",
        )
    )
    contributions = result.scalars().all()

    is_contributor = any(c.contributor_user_id == current_user.id for c in contributions)

    if not is_organizer and not is_contributor and not is_owner_with_names:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    members = [
        GroupGiftMemberSummary(
            user_id=gift.organizer_user_id,
            role="organizer",
            first_name=gift.organizer.first_name if gift.organizer else None,
            username=gift.organizer.username if gift.organizer else None,
        )
    ]
    members.extend(
        GroupGiftMemberSummary(
            user_id=c.contributor_user_id,
            contribution_id=c.id,
            role="contributor",
            first_name=c.contributor.first_name if c.contributor else None,
            username=c.contributor.username if c.contributor else None,
            amount=c.amount if is_organizer else None,
            status=c.status,
            created_at=c.created_at,
        )
        for c in contributions
    )
    return members


async def _notify_goal_reached(db: AsyncSession, gift: GroupGift, redis: Redis | None) -> None:
    """notify contributors that the target is reached without completing the gift"""
    if gift.status != "active":
        return

    result = await db.execute(
        select(GroupGiftContribution).where(
            GroupGiftContribution.group_gift_id == gift.id,
            GroupGiftContribution.status != "cancelled",
        )
    )
    active_contributions = result.scalars().all()

    collected_amount = sum(
        (c.amount for c in active_contributions if c.status in _CONFIRMED_STATUSES),
        Decimal("0"),
    )

    if gift.collection_type == "commit":
        for c in active_contributions:
            if c.status == "pledged":
                c.status = "notified"

    await db.commit()

    if redis and gift.wish:
        await publish_event(redis, "GROUP_GIFT_COMPLETED", {
            "group_gift_id": str(gift.id),
            "wish_id": str(gift.wish_id),
            "wish_title": gift.wish.title,
            "collection_type": gift.collection_type,
            "organizer_user_id": str(gift.organizer_user_id),
            "contributor_user_ids": [str(c.contributor_user_id) for c in active_contributions],
            "total_collected": str(collected_amount),
            "currency": gift.wish.currency or "",
            "payment_method": gift.payment_method,
            "payment_phone": gift.payment_phone,
            "payment_comment": gift.payment_comment or "",
        })


async def _maybe_notify_goal_reached(
    db: AsyncSession,
    gift: GroupGift,
    redis: Redis | None,
    committed_before: Decimal,
) -> None:
    """notify once when the target is crossed; organizer completes explicitly"""
    if gift.status != "active":
        return
    if not gift.wish:
        return
    total_amount = gift.wish.price
    if not total_amount or total_amount <= 0:
        return
    collected_amount = await _compute_collected(db, gift.id)
    if committed_before < total_amount <= collected_amount:
        await _notify_goal_reached(db, gift, redis)


async def _compute_collected(db: AsyncSession, group_gift_id: UUID) -> Decimal:
    """sum confirmed/pledged/notified contribution amounts"""
    result = await db.execute(
        select(GroupGiftContribution).where(
            GroupGiftContribution.group_gift_id == group_gift_id,
            GroupGiftContribution.status.in_(list(_CONFIRMED_STATUSES)),
        )
    )
    return sum((c.amount for c in result.scalars().all()), Decimal("0"))
