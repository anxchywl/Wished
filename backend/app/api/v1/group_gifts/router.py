# group gifts api routes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.db.models import User
from app.modules.group_gifts import (
    cancel_group_gift,
    confirm_transfer,
    create_group_gift,
    get_gift_members,
    get_group_gift,
    join_group_gift,
    leave_group_gift,
    mark_group_gift_purchased,
    organizer_remove_contribution,
    report_transfer,
    toggle_group_gift_approval,
    update_payment_details,
)
from app.modules.group_gifts.rate_limit import (
    check_contribution_create_limit,
    check_gift_create_limit,
)
from app.modules.group_gifts.schemas import (
    ApprovalRequest,
    ContributionCreateRequest,
    ContributionSummary,
    GroupGiftCreateRequest,
    GroupGiftMemberSummary,
    GroupGiftPaymentDetailsUpdate,
    GroupGiftResponse,
    TransferConfirmRequest,
)

router = APIRouter(tags=["group_gifts"])


@router.post(
    "/wishes/{wish_id}/group-gift",
    response_model=GroupGiftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_group_gift(
    wish_id: UUID,
    payload: GroupGiftCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> GroupGiftResponse:
    await check_gift_create_limit(redis, current_user.id)
    return await create_group_gift(db, current_user, wish_id, payload, redis=redis)


@router.get("/wishes/{wish_id}/group-gift", response_model=GroupGiftResponse, response_model_exclude_none=False)
async def get_wish_group_gift(
    wish_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
) -> GroupGiftResponse | None:
    result = await get_group_gift(db, current_user, wish_id)
    if result is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return result


@router.post(
    "/group-gifts/{group_gift_id}/approve",
    response_model=GroupGiftResponse,
    responses={status.HTTP_204_NO_CONTENT: {"description": "Group gift deleted after unanimous cancel approval"}},
)
async def post_group_gift_approve(
    group_gift_id: UUID,
    body: ApprovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    response: Response,
) -> GroupGiftResponse | None:
    result = await toggle_group_gift_approval(db, current_user, group_gift_id, body.approval_type, redis=redis)
    if result is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return result


@router.patch(
    "/group-gifts/{group_gift_id}/payment-details",
    response_model=GroupGiftResponse,
)
async def patch_group_gift_payment_details(
    group_gift_id: UUID,
    payload: GroupGiftPaymentDetailsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GroupGiftResponse:
    return await update_payment_details(db, current_user, group_gift_id, payload)


@router.post(
    "/group-gifts/{group_gift_id}/purchase",
    response_model=GroupGiftResponse,
)
async def post_group_gift_purchase(
    group_gift_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> GroupGiftResponse:
    return await mark_group_gift_purchased(db, current_user, group_gift_id, redis=redis)


@router.post(
    "/group-gifts/{group_gift_id}/join",
    response_model=ContributionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def post_join_group_gift(
    group_gift_id: UUID,
    payload: ContributionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ContributionSummary:
    await check_contribution_create_limit(redis, current_user.id)
    return await join_group_gift(db, current_user, group_gift_id, payload, redis=redis)


@router.post(
    "/contributions/{contribution_id}/transfer",
    response_model=ContributionSummary,
)
async def post_report_transfer(
    contribution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ContributionSummary:
    return await report_transfer(db, current_user, contribution_id, redis=redis)


@router.post(
    "/contributions/{contribution_id}/confirm",
    response_model=ContributionSummary,
)
async def post_confirm_transfer(
    contribution_id: UUID,
    body: TransferConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ContributionSummary:
    return await confirm_transfer(db, current_user, contribution_id, body.confirmed, redis=redis)


@router.delete("/contributions/{contribution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contribution(
    contribution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    await leave_group_gift(db, current_user, contribution_id, redis=redis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/group-gifts/{group_gift_id}/contributions/{contribution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_gift_contribution(
    group_gift_id: UUID,
    contribution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    await organizer_remove_contribution(db, current_user, group_gift_id, contribution_id, redis=redis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/group-gifts/{group_gift_id}/members", response_model=list[GroupGiftMemberSummary])
async def get_group_gift_members(
    group_gift_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GroupGiftMemberSummary]:
    return await get_gift_members(db, current_user, group_gift_id)
