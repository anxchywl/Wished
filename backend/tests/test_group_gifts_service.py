from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.group_gifts.service import get_group_gift


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


class FakeDb:
    def __init__(self, results: list["FakeResult"]) -> None:
        self.results = results

    async def execute(self, query):  # noqa: ANN001
        return self.results.pop(0)


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
        price=Decimal("100.00"),
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
