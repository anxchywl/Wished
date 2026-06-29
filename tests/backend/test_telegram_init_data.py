import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from app.integrations.telegram import TelegramInitDataError, validate_telegram_init_data


BOT_TOKEN = "123456:test-token"


def test_validate_telegram_init_data_returns_user_data() -> None:
    init_data = _build_init_data(
        {
            "id": 123456789,
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Example",
            "photo_url": "https://example.com/photo.jpg",
            "language_code": "en",
            "is_premium": True,
        },
    )

    user = validate_telegram_init_data(
        init_data=init_data,
        bot_token=BOT_TOKEN,
        max_age_seconds=60,
    )

    assert user.telegram_id == 123456789
    assert user.username == "alice"
    assert user.first_name == "Alice"
    assert user.last_name == "Example"
    assert user.photo_url == "https://example.com/photo.jpg"
    assert user.language_code == "en"
    assert user.is_premium is True


def test_validate_telegram_init_data_rejects_invalid_hash() -> None:
    init_data = _build_init_data({"id": 123456789, "first_name": "Alice"})
    tampered_init_data = init_data.replace("Alice", "Mallory")

    with pytest.raises(TelegramInitDataError):
        validate_telegram_init_data(
            init_data=tampered_init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=60,
        )


def test_validate_telegram_init_data_rejects_expired_auth_date() -> None:
    init_data = _build_init_data(
        {"id": 123456789, "first_name": "Alice"},
        auth_date=datetime.now(UTC) - timedelta(days=2),
    )

    with pytest.raises(TelegramInitDataError):
        validate_telegram_init_data(
            init_data=init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=60,
        )


def _build_init_data(
    user: dict[str, object],
    auth_date: datetime | None = None,
) -> str:
    payload = {
        "auth_date": str(int((auth_date or datetime.now(UTC)).timestamp())),
        "query_id": "test-query",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(payload.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    payload["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)
