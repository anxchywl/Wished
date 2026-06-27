from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import FulfilledWish
from app.modules.wishes.service import _create_fulfilled_records


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDb:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def execute(self, _statement):
        return FakeResult(self.results.pop(0) if self.results else None)


@pytest.mark.asyncio
async def test_create_fulfilled_record_for_booking_and_cancel_reservation() -> None:
    owner_id = uuid4()
    reserver_id = uuid4()
    wish = SimpleNamespace(id=uuid4(), wishlist_id=uuid4(), title="Lamp", group_gift=None)
    reservation = SimpleNamespace(reserver_user_id=reserver_id, status="active")
    db = FakeDb(None, reservation)

    events = await _create_fulfilled_records(db, wish, owner_id)

    assert reservation.status == "cancelled"
    assert len(db.added) == 1
    record = db.added[0]
    assert isinstance(record, FulfilledWish)
    assert record.wish_id == wish.id
    assert record.participant_user_id == reserver_id
    assert record.source == "booking"
    assert events == [{
        "participant_user_id": reserver_id,
        "wish_id": wish.id,
        "wishlist_id": wish.wishlist_id,
        "owner_user_id": owner_id,
        "wish_title": wish.title,
        "source": "booking",
    }]


@pytest.mark.asyncio
async def test_create_fulfilled_records_for_group_gift_archives_participants() -> None:
    owner_id = uuid4()
    organizer_id = uuid4()
    contributor_id = uuid4()
    approval = SimpleNamespace()
    contribution = SimpleNamespace(
        contributor_user_id=contributor_id,
        amount=Decimal("25.00"),
        status="confirmed",
    )
    gift = SimpleNamespace(
        id=uuid4(),
        status="active",
        organizer_user_id=organizer_id,
        contributions=[contribution],
        approvals=[approval],
    )
    wish = SimpleNamespace(id=uuid4(), wishlist_id=uuid4(), title="Lamp", group_gift=gift)
    reservation = SimpleNamespace(status="active")
    db = FakeDb(gift, reservation)

    events = await _create_fulfilled_records(db, wish, owner_id)

    assert gift.status == "archived"
    assert contribution.status == "cancelled"
    assert reservation.status == "cancelled"
    assert db.deleted == [approval]
    assert {record.participant_user_id for record in db.added} == {organizer_id, contributor_id}
    assert {record.source for record in db.added} == {"group_gift"}
    assert {event["participant_user_id"] for event in events} == {organizer_id, contributor_id}
