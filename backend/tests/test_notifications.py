"""notification system tests"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.events import QUEUE_KEY, publish_event
from app.modules.notifications.deep_links import profile_url, wish_url, wishlist_url
from app.modules.notifications.handlers import (
    _actor_name,
    _is_duplicate,
    _text,
    handle_followed,
    handle_group_gift_created,
    handle_wish_created,
    handle_wish_fulfilled,
    handle_wishlist_created,
)
from app.modules.notifications.worker import run_notification_worker


# ---------------------------------------------------------------------------
# deep link generation
# ---------------------------------------------------------------------------

def test_profile_url() -> None:
    assert profile_url("https://app.example.com", "alice") == "https://app.example.com/users?profile=alice"


def test_wishlist_url() -> None:
    wid = uuid4()
    assert wishlist_url("https://app.example.com", "alice", wid) == f"https://app.example.com/users?profile=alice&wishlist={wid}"


def test_wish_url() -> None:
    wid = uuid4()
    wish = uuid4()
    assert wish_url("https://app.example.com", "alice", wid, wish) == f"https://app.example.com/users?profile=alice&wishlist={wid}&wish={wish}"


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

def test_text_defaults_to_english() -> None:
    t = _text(None)
    assert t["followed_title"] == "New follower"


def test_text_russian() -> None:
    t = _text("ru")
    assert t["followed_title"] == "Новый подписчик"


def test_text_kazakh_kk_code() -> None:
    t = _text("kk")
    assert t["followed_title"] == "Жаңа жазылушы"


def test_text_falls_back_for_unknown_lang() -> None:
    t = _text("fr")
    assert t["followed_title"] == "New follower"


# ---------------------------------------------------------------------------
# actor name
# ---------------------------------------------------------------------------

def test_actor_name_full_name() -> None:
    user = SimpleNamespace(first_name="Alice", last_name="Smith", username="asmith")
    assert _actor_name(user) == "Alice Smith"


def test_actor_name_first_only() -> None:
    user = SimpleNamespace(first_name="Bob", last_name=None, username=None)
    assert _actor_name(user) == "Bob"


def test_actor_name_username_fallback() -> None:
    user = SimpleNamespace(first_name=None, last_name=None, username="carol")
    assert _actor_name(user) == "@carol"


def test_actor_name_no_info() -> None:
    user = SimpleNamespace(first_name=None, last_name=None, username=None)
    assert _actor_name(user) == "Someone"


# ---------------------------------------------------------------------------
# event publisher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_event_pushes_to_queue() -> None:
    redis = AsyncMock()
    await publish_event(redis, "FOLLOWED", {"follower_user_id": uuid4(), "followed_user_id": uuid4()})
    redis.rpush.assert_called_once()
    call_args = redis.rpush.call_args
    assert call_args[0][0] == QUEUE_KEY
    data = json.loads(call_args[0][1])
    assert data["type"] == "FOLLOWED"
    assert "event_id" in data
    assert "follower_user_id" in data


@pytest.mark.asyncio
async def test_publish_event_survives_redis_failure() -> None:
    redis = AsyncMock()
    redis.rpush.side_effect = Exception("connection refused")
    # must not raise
    await publish_event(redis, "FOLLOWED", {"follower_user_id": uuid4()})


# ---------------------------------------------------------------------------
# deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_duplicate_first_call_returns_false() -> None:
    redis = AsyncMock()
    redis.set.return_value = True  # SET NX succeeded → first time
    result = await _is_duplicate(redis, "event-abc", 123456)
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_second_call_returns_true() -> None:
    redis = AsyncMock()
    redis.set.return_value = None  # SET NX failed → already exists
    result = await _is_duplicate(redis, "event-abc", 123456)
    assert result is True


# ---------------------------------------------------------------------------
# FOLLOWED handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_followed_sends_notification() -> None:
    follower_id = uuid4()
    followed_id = uuid4()
    event_id = str(uuid4())

    follower = SimpleNamespace(id=follower_id, first_name="Alice", last_name=None, username="alice", language_code="en")
    followed = SimpleNamespace(id=followed_id, telegram_id=999, language_code="en")

    db = _fake_db_for_users({follower_id: follower, followed_id: followed})
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = True  # not duplicate
    redis.incr.return_value = 1  # outbound rate check passes

    await handle_followed(
        {"type": "FOLLOWED", "event_id": event_id, "follower_user_id": str(follower_id), "followed_user_id": str(followed_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_called_once()
    call = bot.send_message.call_args
    assert call.kwargs["chat_id"] == 999
    assert "Alice" in call.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_followed_skips_duplicate() -> None:
    follower_id = uuid4()
    followed_id = uuid4()

    follower = SimpleNamespace(id=follower_id, first_name="Alice", last_name=None, username="alice", language_code="en")
    followed = SimpleNamespace(id=followed_id, telegram_id=999, language_code="en")

    db = _fake_db_for_users({follower_id: follower, followed_id: followed})
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = None  # duplicate

    await handle_followed(
        {"type": "FOLLOWED", "event_id": str(uuid4()), "follower_user_id": str(follower_id), "followed_user_id": str(followed_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_followed_survives_telegram_failure() -> None:
    follower_id = uuid4()
    followed_id = uuid4()

    follower = SimpleNamespace(id=follower_id, first_name="Alice", last_name=None, username="alice", language_code="en")
    followed = SimpleNamespace(id=followed_id, telegram_id=999, language_code="en")

    db = _fake_db_for_users({follower_id: follower, followed_id: followed})
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Telegram API error")
    redis = AsyncMock()
    redis.set.return_value = True

    # must not raise
    await handle_followed(
        {"type": "FOLLOWED", "event_id": str(uuid4()), "follower_user_id": str(follower_id), "followed_user_id": str(followed_id)},
        db, bot, redis, "https://app.example.com",
    )


@pytest.mark.asyncio
async def test_handle_followed_missing_follower_is_noop() -> None:
    followed_id = uuid4()
    db = _fake_db_returning_none()
    bot = AsyncMock()
    redis = AsyncMock()

    await handle_followed(
        {"type": "FOLLOWED", "event_id": str(uuid4()), "follower_user_id": str(uuid4()), "followed_user_id": str(followed_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# WISHLIST_CREATED handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_wishlist_created_notifies_followers() -> None:
    owner_id = uuid4()
    wishlist_id = uuid4()
    follower_tg_id = 777

    owner = SimpleNamespace(id=owner_id, first_name="Bob", last_name=None, username="bob", language_code="en")
    wishlist = SimpleNamespace(id=wishlist_id, title="My Birthday List", visibility="public")

    db = _fake_db_wishlist_created(owner, wishlist, followers=[(follower_tg_id, "en")])
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = True  # not duplicate, not batched
    redis.incr.return_value = 1  # outbound rate check passes

    await handle_wishlist_created(
        {"type": "WISHLIST_CREATED", "event_id": str(uuid4()), "wishlist_id": str(wishlist_id), "owner_user_id": str(owner_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_called_once()
    call = bot.send_message.call_args
    assert call.kwargs["chat_id"] == follower_tg_id
    assert "My Birthday List" in call.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_wishlist_created_skips_private_wishlist() -> None:
    owner_id = uuid4()
    wishlist_id = uuid4()

    owner = SimpleNamespace(id=owner_id, first_name="Bob", last_name=None, username="bob", language_code="en")
    wishlist = SimpleNamespace(id=wishlist_id, title="Secret List", visibility="private")

    db = _fake_db_wishlist_created(owner, wishlist, followers=[(888, "en")])
    bot = AsyncMock()
    redis = AsyncMock()

    await handle_wishlist_created(
        {"type": "WISHLIST_CREATED", "event_id": str(uuid4()), "wishlist_id": str(wishlist_id), "owner_user_id": str(owner_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# WISH_CREATED handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_wish_created_notifies_followers() -> None:
    owner_id = uuid4()
    wishlist_id = uuid4()
    wish_id = uuid4()
    follower_tg_id = 555

    owner = SimpleNamespace(id=owner_id, first_name="Carol", last_name=None, username="carol", language_code="en")
    wishlist = SimpleNamespace(id=wishlist_id, title="Wishlist", visibility="public")
    wish = SimpleNamespace(id=wish_id, title="New Sneakers", wishlist_id=wishlist_id)

    db = _fake_db_wish(owner, wishlist, wish, followers=[(follower_tg_id, "en")])
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = True  # not duplicate, not batched
    redis.incr.return_value = 1  # outbound rate check passes

    await handle_wish_created(
        {"type": "WISH_CREATED", "event_id": str(uuid4()), "wish_id": str(wish_id), "wishlist_id": str(wishlist_id), "owner_user_id": str(owner_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_called_once()
    call = bot.send_message.call_args
    assert call.kwargs["chat_id"] == follower_tg_id
    assert "New Sneakers" in call.kwargs["text"]
    url = call.kwargs["reply_markup"].inline_keyboard[0][0].web_app.url
    assert str(wish_id) in url
    assert str(owner_id) in url


# ---------------------------------------------------------------------------
# WISH_FULFILLED handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_wish_fulfilled_notifies_followers() -> None:
    owner_id = uuid4()
    wishlist_id = uuid4()
    wish_id = uuid4()
    follower_tg_id = 444

    owner = SimpleNamespace(id=owner_id, first_name="Dave", last_name=None, username="dave", language_code="en")
    wishlist = SimpleNamespace(id=wishlist_id, title="Dave's List", visibility="public")
    wish = SimpleNamespace(id=wish_id, title="Guitar", wishlist_id=wishlist_id)

    db = _fake_db_wish(owner, wishlist, wish, followers=[(follower_tg_id, "ru")])
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = True  # not duplicate, not batched
    redis.incr.return_value = 1  # outbound rate check passes

    await handle_wish_fulfilled(
        {"type": "WISH_FULFILLED", "event_id": str(uuid4()), "wish_id": str(wish_id), "wishlist_id": str(wishlist_id), "owner_user_id": str(owner_id)},
        db, bot, redis, "https://app.example.com",
    )

    bot.send_message.assert_called_once()
    call = bot.send_message.call_args
    assert "Guitar" in call.kwargs["text"]
    # button opens wishlist, not the wish itself
    url = call.kwargs["reply_markup"].inline_keyboard[0][0].web_app.url
    assert str(wishlist_id) in url
    assert "wish=" not in url


# ---------------------------------------------------------------------------
# privacy: no reservation info leaks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wish_fulfilled_text_contains_no_reservation_info() -> None:
    owner_id = uuid4()
    wishlist_id = uuid4()
    wish_id = uuid4()

    owner = SimpleNamespace(id=owner_id, first_name="Eve", last_name=None, username="eve", language_code="en")
    wishlist = SimpleNamespace(id=wishlist_id, title="List", visibility="public")
    wish = SimpleNamespace(id=wish_id, title="Book", wishlist_id=wishlist_id)

    db = _fake_db_wish(owner, wishlist, wish, followers=[(123, "en")])
    bot = AsyncMock()
    redis = AsyncMock()
    redis.set.return_value = True  # not duplicate, not batched
    redis.incr.return_value = 1  # outbound rate check passes

    await handle_wish_fulfilled(
        {"type": "WISH_FULFILLED", "event_id": str(uuid4()), "wish_id": str(wish_id), "wishlist_id": str(wishlist_id), "owner_user_id": str(owner_id)},
        db, bot, redis, "https://app.example.com",
    )

    text = bot.send_message.call_args.kwargs["text"]
    for forbidden in ["reserved", "reserver", "reservation", "booked", "booking"]:
        assert forbidden not in text.lower()


@pytest.mark.asyncio
async def test_group_gift_created_notification_is_muted() -> None:
    bot = AsyncMock()
    db = AsyncMock()
    redis = AsyncMock()

    await handle_group_gift_created(
        {
            "type": "GROUP_GIFT_CREATED",
            "event_id": str(uuid4()),
            "wishlist_owner_user_id": str(uuid4()),
            "wish_title": "Book",
        },
        db,
        bot,
        redis,
        "https://app.example.com",
    )

    bot.send_message.assert_not_called()
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# worker dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_dispatches_followed_event() -> None:
    from app.modules.notifications import worker as worker_module

    event = {
        "type": "FOLLOWED",
        "event_id": str(uuid4()),
        "follower_user_id": str(uuid4()),
        "followed_user_id": str(uuid4()),
    }

    dispatched = []

    async def fake_handle_followed(ev, db, b, r, url):
        dispatched.append(ev)

    redis = AsyncMock()
    redis.blpop.side_effect = [
        ("notifications:queue", json.dumps(event)),
        asyncio.CancelledError(),
    ]

    bot = AsyncMock()
    session_factory = MagicMock()

    with patch.object(worker_module, "_HANDLERS", {"FOLLOWED": fake_handle_followed}):
        task = asyncio.create_task(
            run_notification_worker(redis, bot, session_factory, "https://app.example.com")
        )
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    assert len(dispatched) == 1
    assert dispatched[0]["type"] == "FOLLOWED"


@pytest.mark.asyncio
async def test_worker_skips_unknown_event_type() -> None:

    event = {"type": "UNKNOWN_TYPE", "event_id": str(uuid4())}
    dispatched = []

    async def fake_handle_any(ev, db, b, r, url):
        dispatched.append(ev)

    redis = AsyncMock()
    redis.blpop.side_effect = [
        ("notifications:queue", json.dumps(event)),
        asyncio.CancelledError(),
    ]

    bot = AsyncMock()
    session_factory = MagicMock()

    task = asyncio.create_task(
        run_notification_worker(redis, bot, session_factory, "https://app.example.com")
    )
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert dispatched == []


# ---------------------------------------------------------------------------
# helper fakes
# ---------------------------------------------------------------------------

def _make_result(scalar=None, rows=None):
    """build a sync-compatible result mock"""
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    r.all.return_value = rows or []
    return r


def _fake_db_for_users(users_by_id: dict) -> AsyncMock:
    """fake db returning users in insertion order on each call"""
    db = AsyncMock()
    ordered = list(users_by_id.values())
    call_count = [0]

    async def execute(stmt):
        user = ordered[call_count[0] % len(ordered)]
        call_count[0] += 1
        return _make_result(scalar=user)

    db.execute = execute
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=None)
    return db


def _fake_db_returning_none() -> AsyncMock:
    db = AsyncMock()

    async def execute(stmt):
        return _make_result(scalar=None)

    db.execute = execute
    return db


def _fake_db_wishlist_created(owner, wishlist, followers: list[tuple[int, str | None]]):
    """fake db for wishlist_created handler: returns owner, wishlist, then followers"""
    db = AsyncMock()
    call_count = [0]

    async def execute(stmt):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return _make_result(scalar=owner)
        if n == 1:
            return _make_result(scalar=wishlist)
        return _make_result(rows=followers)

    db.execute = execute
    return db


def _fake_db_wish(owner, wishlist, wish, followers: list[tuple[int, str | None]]):
    """fake db for wish_created / wish_fulfilled handler: owner, wishlist, wish, followers"""
    db = AsyncMock()
    call_count = [0]

    async def execute(stmt):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return _make_result(scalar=owner)
        if n == 1:
            return _make_result(scalar=wishlist)
        if n == 2:
            return _make_result(scalar=wish)
        return _make_result(rows=followers)

    db.execute = execute
    return db
