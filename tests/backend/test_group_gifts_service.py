from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from app.modules.group_gifts.service import (
    create_group_gift,
    get_gift_members,
    get_group_gift,
    join_group_gift,
    mark_group_gift_purchased,
    toggle_group_gift_approval,
    update_payment_details,
)


@pytest.mark.asyncio
async def test_owner_hide_visibility_returns_no_group_gift() -> None:
    owner_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=uuid4())
    db = FakeDb(
        [
            FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
            FakeResult(gift),
        ]
    )

    response = await get_group_gift(
        db,
        _user(user_id=owner_id, group_gift_visibility="hide"),
        wish_id,
    )

    assert response is None


@pytest.mark.asyncio
async def test_blocked_organizer_returns_cancelled_without_payment_fields() -> None:
    viewer_id = uuid4()
    owner_id = uuid4()
    wish_id = uuid4()
    organizer_id = uuid4()
    db = FakeDb(
        [
            FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
            FakeResult(
                _gift(
                    wish_id=wish_id,
                    organizer_user_id=organizer_id,
                    organizer=_user(user_id=organizer_id, is_blocked=True),
                )
            ),
        ]
    )

    response = await get_group_gift(db, _user(user_id=viewer_id), wish_id)

    assert response is not None
    assert response.status == "cancelled"
    assert response.payment_method is None
    assert response.payment_phone is None
    assert response.payment_comment is None


@pytest.mark.asyncio
async def test_non_owner_create_group_gift_becomes_organizer() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    db = FakeDb(
        [
            FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
            FakeResult(None),
            FakeResult(None),
        ]
    )

    response = await create_group_gift(
        db,
        _user(user_id=organizer_id),
        wish_id,
        SimpleNamespace(
            collection_type="immediate",
            payment_method="Kaspi",
            payment_phone="+7 777 777 77 77",
            payment_comment=None,
        ),
    )

    assert db.added is not None
    assert db.added.organizer_user_id == organizer_id
    assert response.is_organizer is True
    assert response.payment_method == "Kaspi"


@pytest.mark.asyncio
async def test_create_group_gift_optional_phone() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    db = FakeDb(
        [
            FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
            FakeResult(None),
            FakeResult(None),
        ]
    )

    response = await create_group_gift(
        db,
        _user(user_id=organizer_id),
        wish_id,
        SimpleNamespace(
            collection_type="immediate",
            payment_method="Kaspi",
            payment_phone=None,
            payment_comment=None,
        ),
    )

    assert db.added is not None
    assert db.added.organizer_user_id == organizer_id
    assert response.is_organizer is True
    assert response.payment_phone is None


@pytest.mark.asyncio
async def test_owner_cannot_create_group_gift_for_own_wish() -> None:
    owner_id = uuid4()
    wish_id = uuid4()
    db = FakeDb([FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id))])

    with pytest.raises(HTTPException) as exc:
        await create_group_gift(
            db,
            _user(user_id=owner_id),
            wish_id,
            SimpleNamespace(
                collection_type="immediate",
                payment_method="Kaspi",
                payment_phone="+7 777 777 77 77",
                payment_comment=None,
            ),
        )

    assert exc.value.status_code == 400
    assert (
        exc.value.detail == "Wish owner cannot organize a group gift on their own wish"
    )


@pytest.mark.asyncio
async def test_wish_owner_can_join_group_gift_organized_by_someone_else() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=owner_id)
    db = FakeDb(
        [
            FakeResult(gift),
            FakeResult(None),
            FakeResult([]),
        ]
    )

    response = await join_group_gift(
        db,
        _user(user_id=owner_id),
        gift.id,
        SimpleNamespace(amount=Decimal("25.00")),
    )

    assert db.added is not None
    assert db.added.contributor_user_id == owner_id
    assert response.status == "waiting_transfer"


@pytest.mark.asyncio
async def test_organizer_can_join_their_own_group_gift() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    db = FakeDb(
        [
            FakeResult(gift),
            FakeResult(None),
            FakeResult([]),
        ]
    )

    response = await join_group_gift(
        db,
        _user(user_id=organizer_id),
        gift.id,
        SimpleNamespace(amount=Decimal("35.00")),
    )

    assert db.added is not None
    assert db.added.contributor_user_id == organizer_id
    assert response.amount == Decimal("35.00")


@pytest.mark.asyncio
async def test_join_rejects_amount_above_remaining_target() -> None:
    contributor_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    existing = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=uuid4(),
        contributor=_user(),
        amount=Decimal("75.00"),
    )
    db = FakeDb(
        [
            FakeResult(gift),
            FakeResult(None),
            FakeResult([existing]),
        ]
    )

    with pytest.raises(HTTPException) as exc:
        await join_group_gift(
            db,
            _user(user_id=contributor_id),
            gift.id,
            SimpleNamespace(amount=Decimal("30.00")),
        )

    assert exc.value.status_code == 400
    assert "Contribution exceeds remaining amount" in exc.value.detail
    assert db.added is None


@pytest.mark.asyncio
async def test_commit_goal_reached_keeps_gift_active_until_organizer_completes() -> (
    None
):
    contributor_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.collection_type = "commit"
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    existing = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=uuid4(),
        contributor=_user(),
        amount=Decimal("75.00"),
        status="pledged",
    )
    new_contribution = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=contributor_id,
        contributor=_user(user_id=contributor_id),
        amount=Decimal("25.00"),
        status="pledged",
    )
    db = FakeDb(
        [
            FakeResult(gift),
            FakeResult(None),
            FakeResult([existing]),
            FakeResult([existing, new_contribution]),
            FakeResult([existing, new_contribution]),
        ]
    )

    response = await join_group_gift(
        db,
        _user(user_id=contributor_id),
        gift.id,
        SimpleNamespace(amount=Decimal("25.00")),
    )

    assert response.status == "pledged"
    assert gift.status == "active"
    assert existing.status == "notified"


@pytest.mark.asyncio
async def test_members_include_creator_and_hide_amounts_from_owner() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    contributor_id = uuid4()
    wish_id = uuid4()
    gift = _gift(
        wish_id=wish_id,
        organizer_user_id=organizer_id,
        organizer=_user(user_id=organizer_id, username="maker", first_name="Maker"),
    )
    gift.wish = _wish(wish_id=wish_id, owner_user_id=owner_id)
    contribution = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=contributor_id,
        contributor=_user(
            user_id=contributor_id, username="friend", first_name="Friend"
        ),
        status="confirmed",
    )
    db = FakeDb([FakeResult(gift), FakeResult([contribution])])

    response = await get_gift_members(
        db,
        _user(user_id=owner_id, group_gift_visibility="names"),
        gift.id,
    )

    assert [member.role for member in response] == ["organizer", "contributor"]
    assert response[0].username == "maker"
    assert response[1].username == "friend"
    assert response[1].amount is None


@pytest.mark.asyncio
async def test_members_show_amounts_to_organizer() -> None:
    organizer_id = uuid4()
    contributor_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    contribution = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=contributor_id,
        contributor=_user(user_id=contributor_id),
        status="confirmed",
    )
    db = FakeDb([FakeResult(gift), FakeResult([contribution])])

    response = await get_gift_members(db, _user(user_id=organizer_id), gift.id)

    assert response[1].amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_immediate_pending_transfer_is_not_listed_as_contributor() -> None:
    organizer_id = uuid4()
    contributor_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    contribution = _contribution(
        group_gift_id=gift.id,
        contributor_user_id=contributor_id,
        contributor=_user(user_id=contributor_id),
        status="waiting_confirmation",
    )
    db = FakeDb([FakeResult(gift), FakeResult([contribution])])

    response = await get_gift_members(db, _user(user_id=organizer_id), gift.id)

    assert [member.role for member in response] == ["organizer"]


@pytest.mark.asyncio
async def test_organizer_can_update_payment_details() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=owner_id)
    db = FakeDb([FakeResult(gift)])

    response = await update_payment_details(
        db,
        _user(user_id=organizer_id),
        gift.id,
        SimpleNamespace(
            payment_method="Halyk",
            payment_phone="+7 700 000 00 00",
            payment_comment="new comment",
        ),
    )

    assert db.committed is True
    assert gift.payment_method == "Halyk"
    assert gift.payment_phone == "+7 700 000 00 00"
    assert gift.payment_comment == "new comment"
    assert response.payment_method == "Halyk"


@pytest.mark.asyncio
async def test_non_organizer_cannot_update_payment_details() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    db = FakeDb([FakeResult(gift)])

    with pytest.raises(HTTPException) as exc:
        await update_payment_details(
            db,
            _user(user_id=uuid4()),
            gift.id,
            SimpleNamespace(
                payment_method="Halyk",
                payment_phone="+7 700 000 00 00",
                payment_comment=None,
            ),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Not the organizer"
    assert db.committed is False


@pytest.mark.asyncio
async def test_organizer_can_mark_group_gift_purchased_for_existing_active_wish() -> (
    None
):
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=owner_id)
    db = FakeDb([FakeResult(gift), FakeResult(None)])

    response = await mark_group_gift_purchased(
        db,
        _user(user_id=organizer_id),
        gift.id,
    )

    assert db.committed is True
    assert gift.status == "completed"
    assert gift.wish.status == "active"
    assert db.added.wish_id == wish_id
    assert db.added.reserver_user_id == organizer_id
    assert db.added.status == "active"
    assert response.status == "completed"


@pytest.mark.asyncio
async def test_non_organizer_cannot_mark_group_gift_purchased() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    db = FakeDb([FakeResult(gift)])

    with pytest.raises(HTTPException) as exc:
        await mark_group_gift_purchased(
            db,
            _user(user_id=uuid4()),
            gift.id,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Not the organizer"
    assert db.committed is False


def _gift_with_approvals(
    wish_id,  # noqa: ANN001
    organizer_user_id,  # noqa: ANN001
    approvals: list | None = None,
    status: str = "active",
) -> SimpleNamespace:
    g = _gift(wish_id=wish_id, organizer_user_id=organizer_user_id)
    g.status = status
    g.approvals = approvals or []
    return g


def _approval(group_gift_id, user_id, approval_type: str = "cancel") -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(
        id=uuid4(),
        group_gift_id=group_gift_id,
        user_id=user_id,
        approval_type=approval_type,
    )


@pytest.mark.asyncio
async def test_non_participant_cannot_toggle_approval() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift_with_approvals(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())
    db = FakeDb([FakeResult(gift)])

    with pytest.raises(HTTPException) as exc:
        await toggle_group_gift_approval(db, _user(user_id=uuid4()), gift.id, "cancel")

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_organizer_approval_with_no_contributors_cancels_immediately() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift_with_approvals(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())

    # single query: gift loaded in-memory; _execute_cancel queries for Reservation (returns None)
    db = FakeDb(
        [
            FakeResult(gift),
            FakeResult(None),  # Reservation lookup in _execute_cancel
        ]
    )

    result = await toggle_group_gift_approval(
        db, _user(user_id=organizer_id), gift.id, "cancel"
    )

    # unanimous (1/1) → deletes gift, returns None
    assert result is None
    assert db.deleted is gift


@pytest.mark.asyncio
async def test_organizer_approval_with_contributor_is_partial() -> None:
    organizer_id = uuid4()
    contributor_id = uuid4()
    wish_id = uuid4()
    gift = _gift_with_approvals(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.collection_type = "commit"
    contributor = _user(user_id=contributor_id)
    gift.contributions = [
        _contribution(gift.id, contributor_id, contributor, status="pledged")
    ]
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())

    # single query: gift loaded in-memory; 1 of 2 participants → not unanimous
    db = FakeDb([FakeResult(gift)])

    result = await toggle_group_gift_approval(
        db, _user(user_id=organizer_id), gift.id, "cancel"
    )

    # not unanimous — gift survives, response returned with 1 cancel approval
    assert result is not None
    assert result.cancel_approval_count == 1
    assert result.participant_count == 2
    assert db.deleted is None


@pytest.mark.asyncio
async def test_revoking_existing_approval_removes_it() -> None:
    organizer_id = uuid4()
    wish_id = uuid4()
    existing = _approval(uuid4(), organizer_id)
    # gift already has the approval in-memory — no separate DB query for it
    gift = _gift_with_approvals(
        wish_id=wish_id, organizer_user_id=organizer_id, approvals=[existing]
    )
    gift.wish = _wish(wish_id=wish_id, owner_user_id=uuid4())

    db = FakeDb([FakeResult(gift)])

    result = await toggle_group_gift_approval(
        db, _user(user_id=organizer_id), gift.id, "cancel"
    )

    assert result is not None
    assert result.cancel_approval_count == 0
    assert db.deleted is existing


class FakeDb:
    def __init__(self, results: list["FakeResult"]) -> None:
        self.results = results
        self.added = None
        self.deleted = None
        self.committed = False

    async def execute(self, query):  # noqa: ANN001
        return self.results.pop(0)

    def add(self, value) -> None:  # noqa: ANN001
        self.added = value

    async def delete(self, value) -> None:  # noqa: ANN001
        self.deleted = value

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def get(self, model, pk):  # noqa: ANN001
        return SimpleNamespace(
            group_gift_visibility="anonymous", booking_visibility="anonymous"
        )

    async def refresh(self, value) -> None:  # noqa: ANN001
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


class FakeResult:
    def __init__(self, value) -> None:  # noqa: ANN001
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return FakeScalars(self.value)


class FakeScalars:
    def __init__(self, value) -> None:  # noqa: ANN001
        self.value = value

    def all(self):
        return self.value


def _user(
    user_id=None,  # noqa: ANN001
    username: str = "alice",
    first_name: str = "Alice",
    group_gift_visibility: str = "hide",
    is_blocked: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id or uuid4(),
        username=username,
        first_name=first_name,
        group_gift_visibility=group_gift_visibility,
        is_blocked=is_blocked,
    )


def _wish(wish_id, owner_user_id) -> SimpleNamespace:  # noqa: ANN001
    return SimpleNamespace(
        id=wish_id,
        wishlist_id=uuid4(),
        title="Tea set",
        status="active",
        price=Decimal("100.00"),
        currency="KZT",
        wishlist=SimpleNamespace(owner_user_id=owner_user_id, visibility="public"),
    )


def _gift(
    wish_id,  # noqa: ANN001
    organizer_user_id,  # noqa: ANN001
    organizer: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        wish_id=wish_id,
        organizer_user_id=organizer_user_id,
        collection_type="immediate",
        status="active",
        payment_method="Kaspi",
        payment_phone="+7 777 777 77 77",
        payment_comment="comment",
        contributions=[],
        approvals=[],
        organizer=organizer or _user(user_id=organizer_user_id),
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )


def _contribution(
    group_gift_id,  # noqa: ANN001
    contributor_user_id,  # noqa: ANN001
    contributor: SimpleNamespace,
    amount: Decimal = Decimal("25.00"),
    status: str = "pledged",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        group_gift_id=group_gift_id,
        contributor_user_id=contributor_user_id,
        contributor=contributor,
        amount=amount,
        status=status,
        created_at=datetime(2026, 6, 25, 12, 5, tzinfo=UTC),
    )
