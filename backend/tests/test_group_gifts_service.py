from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from app.modules.group_gifts.service import (
    create_group_gift,
    get_group_gift,
    join_group_gift,
    mark_group_gift_purchased,
    update_payment_details,
)


@pytest.mark.asyncio
async def test_owner_hide_visibility_returns_no_group_gift() -> None:
    owner_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=uuid4())
    db = FakeDb([
        FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
        FakeResult(gift),
    ])

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
    db = FakeDb([
        FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
        FakeResult(
            _gift(
                wish_id=wish_id,
                organizer_user_id=organizer_id,
                organizer=_user(user_id=organizer_id, is_blocked=True),
            )
        ),
    ])

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
    db = FakeDb([
        FakeResult(_wish(wish_id=wish_id, owner_user_id=owner_id)),
        FakeResult(None),
        FakeResult(None),
    ])

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
    assert exc.value.detail == "Wish owner cannot organize a group gift on their own wish"


@pytest.mark.asyncio
async def test_wish_owner_can_join_group_gift_organized_by_someone_else() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    wish_id = uuid4()
    gift = _gift(wish_id=wish_id, organizer_user_id=organizer_id)
    gift.wish = _wish(wish_id=wish_id, owner_user_id=owner_id)
    db = FakeDb([
        FakeResult(gift),
        FakeResult(None),
    ])

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
async def test_organizer_can_mark_group_gift_purchased_for_existing_active_wish() -> None:
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
    assert gift.wish.status == "completed"
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


class FakeDb:
    def __init__(self, results: list["FakeResult"]) -> None:
        self.results = results
        self.added = None
        self.committed = False

    async def execute(self, query):  # noqa: ANN001
        return self.results.pop(0)

    def add(self, value) -> None:  # noqa: ANN001
        self.added = value

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

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


def _user(
    user_id=None,  # noqa: ANN001
    group_gift_visibility: str = "hide",
    is_blocked: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id or uuid4(),
        username="alice",
        first_name="Alice",
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
        organizer=organizer or _user(user_id=organizer_user_id),
        created_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )
