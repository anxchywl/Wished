from __future__ import annotations

import logging
from typing import Annotated
from datetime import datetime, UTC, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_admin
from app.api.deps.database import get_db_session
from app.db.models.audit_log import AuditLog
from app.db.models.follows import Follow
from app.db.models.reservations import Reservation
from app.db.models.users import User
from app.db.models.wish_images import WishImage
from app.db.models.wishes import Wish
from app.db.models.wishlists import Wishlist
from app.api.v1.admin.schemas import (
    AdminMeResponse,
    AdminMediaItem,
    AdminStatsResponse,
    AdminUserItem,
    AdminWishItem,
    AdminWishlistItem,
    AuditLogItem,
)

logger = logging.getLogger("app.api.v1.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


async def _write_audit_log(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(AuditLog(
        actor_user_id=admin.id,
        actor_telegram_id=admin.telegram_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
    ))


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    admin: Annotated[User, Depends(require_admin)],
) -> AdminMeResponse:
    """confirm admin identity"""
    return AdminMeResponse(is_admin=True, telegram_id=admin.telegram_id)


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """return aggregate platform counts"""
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.last_login_at >= thirty_days_ago)
    )).scalar() or 0
    total_wishlists = (await db.execute(select(func.count()).select_from(Wishlist))).scalar() or 0
    total_wishes = (await db.execute(select(func.count()).select_from(Wish))).scalar() or 0
    active_wishes = (await db.execute(
        select(func.count()).select_from(Wish).where(Wish.status == "active")
    )).scalar() or 0
    total_reservations = (await db.execute(
        select(func.count()).select_from(Reservation).where(Reservation.status == "active")
    )).scalar() or 0
    total_wish_media = (await db.execute(select(func.count()).select_from(WishImage))).scalar() or 0
    total_wishlist_covers = (await db.execute(
        select(func.count()).select_from(Wishlist).where(Wishlist.cover_image_object_name.isnot(None))
    )).scalar() or 0
    total_media = total_wish_media + total_wishlist_covers
    total_follows = (await db.execute(select(func.count()).select_from(Follow))).scalar() or 0

    await _write_audit_log(db, admin, "viewed_stats")
    await db.commit()

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_wishlists=total_wishlists,
        total_wishes=total_wishes,
        active_wishes=active_wishes,
        total_reservations=total_reservations,
        total_media=total_media,
        total_follows=total_follows,
    )


@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(default=None, max_length=100),
) -> list[AdminUserItem]:
    """list users with optional search by username or name"""
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if q:
        needle = f"%{q.strip()}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                User.username.ilike(needle),
                User.first_name.ilike(needle),
                User.last_name.ilike(needle),
            )
        )
    users = list((await db.execute(stmt)).scalars().all())

    result = []
    for u in users:
        wishlist_count = (await db.execute(
            select(func.count()).select_from(Wishlist).where(Wishlist.owner_user_id == u.id)
        )).scalar() or 0
        wish_count = (await db.execute(
            select(func.count()).select_from(Wish).join(Wishlist).where(Wishlist.owner_user_id == u.id)
        )).scalar() or 0
        result.append(AdminUserItem(
            id=u.id,
            telegram_id=u.telegram_id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            photo_url=u.photo_url,
            created_at=u.created_at.isoformat(),
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            wishlist_count=wishlist_count,
            wish_count=wish_count,
        ))

    await _write_audit_log(db, admin, "viewed_users", metadata={"q": q, "limit": limit, "offset": offset})
    await db.commit()
    return result


@router.get("/wishlists", response_model=list[AdminWishlistItem])
async def list_wishlists(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    visibility: str | None = Query(default=None, max_length=32),
) -> list[AdminWishlistItem]:
    """list all wishlists for moderation"""
    stmt = select(Wishlist, User).join(User, Wishlist.owner_user_id == User.id).order_by(Wishlist.created_at.desc()).limit(limit).offset(offset)
    if visibility in ("public", "private", "friends"):
        stmt = stmt.where(Wishlist.visibility == visibility)
    rows = list((await db.execute(stmt)).all())

    result = []
    for wishlist, owner in rows:
        wish_count = (await db.execute(
            select(func.count()).select_from(Wish).where(Wish.wishlist_id == wishlist.id)
        )).scalar() or 0
        result.append(AdminWishlistItem(
            id=wishlist.id,
            owner_telegram_id=owner.telegram_id,
            owner_username=owner.username,
            title=wishlist.title,
            visibility=wishlist.visibility,
            wish_count=wish_count,
            created_at=wishlist.created_at.isoformat(),
        ))

    await _write_audit_log(db, admin, "viewed_wishlists", metadata={"limit": limit, "offset": offset})
    await db.commit()
    return result


@router.get("/wishes", response_model=list[AdminWishItem])
async def list_wishes(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    wish_status: str | None = Query(default=None, max_length=32),
) -> list[AdminWishItem]:
    """list wishes for content moderation"""
    stmt = (
        select(Wish, User)
        .join(Wishlist, Wish.wishlist_id == Wishlist.id)
        .join(User, Wishlist.owner_user_id == User.id)
        .order_by(Wish.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if wish_status in ("active", "completed", "archived"):
        stmt = stmt.where(Wish.status == wish_status)
    rows = list((await db.execute(stmt)).all())

    result = []
    for wish, owner in rows:
        has_reservation = bool((await db.execute(
            select(func.count()).select_from(Reservation).where(
                Reservation.wish_id == wish.id,
                Reservation.status == "active",
            )
        )).scalar())
        image_count = (await db.execute(
            select(func.count()).select_from(WishImage).where(WishImage.wish_id == wish.id)
        )).scalar() or 0
        result.append(AdminWishItem(
            id=wish.id,
            wishlist_id=wish.wishlist_id,
            owner_telegram_id=owner.telegram_id,
            title=wish.title,
            status=wish.status,
            created_at=wish.created_at.isoformat(),
            has_reservation=has_reservation,
            image_count=image_count,
        ))

    await _write_audit_log(db, admin, "viewed_wishes", metadata={"limit": limit, "offset": offset})
    await db.commit()
    return result


@router.get("/media", response_model=list[AdminMediaItem])
async def list_media(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AdminMediaItem]:
    """list uploaded media for management"""
    stmt = (
        select(WishImage, User)
        .join(Wish, WishImage.wish_id == Wish.id)
        .join(Wishlist, Wish.wishlist_id == Wishlist.id)
        .join(User, Wishlist.owner_user_id == User.id)
        .order_by(WishImage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.execute(stmt)).all())

    result = [
        AdminMediaItem(
            id=img.id,
            wish_id=img.wish_id,
            owner_telegram_id=owner.telegram_id,
            object_name=img.object_name,
            status=img.status,
            created_at=img.created_at.isoformat(),
        )
        for img, owner in rows
    ]

    await _write_audit_log(db, admin, "viewed_media", metadata={"limit": limit, "offset": offset})
    await db.commit()
    return result


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def list_audit_logs(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AuditLogItem]:
    """list recent admin audit log entries"""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    logs = list((await db.execute(stmt)).scalars().all())

    return [
        AuditLogItem(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_telegram_id=log.actor_telegram_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            metadata_json=log.metadata_json,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
