import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl


class TelegramInitDataError(Exception):
    """telegram auth error"""

    pass


@dataclass(frozen=True)
class TelegramUserData:
    """telegram user payload"""

    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    language_code: str | None
    is_premium: bool | None


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int,
) -> TelegramUserData:
    """validate telegram init data"""
    if not bot_token:
        raise TelegramInitDataError("Telegram bot token is not configured")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramInitDataError("Telegram init data hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramInitDataError("Telegram init data hash is invalid")

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw:
        raise TelegramInitDataError("Telegram auth_date is missing")

    try:
        auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=UTC)
    except ValueError as exc:
        raise TelegramInitDataError("Telegram auth_date is invalid") from exc

    age_seconds = (datetime.now(UTC) - auth_date).total_seconds()
    if age_seconds > max_age_seconds:
        raise TelegramInitDataError("Telegram init data is expired")
    # reject timestamps from the future (small skew allowed) so a forged auth_date
    # cannot produce a never-expiring payload
    if age_seconds < -60:
        raise TelegramInitDataError("Telegram auth_date is in the future")

    user_raw = parsed.get("user")
    if not user_raw:
        raise TelegramInitDataError("Telegram user payload is missing")

    try:
        user_payload: dict[str, Any] = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramInitDataError("Telegram user payload is invalid") from exc

    telegram_id = user_payload.get("id")
    if not isinstance(telegram_id, int):
        raise TelegramInitDataError("Telegram user id is invalid")

    return TelegramUserData(
        telegram_id=telegram_id,
        username=_optional_string(user_payload.get("username")),
        first_name=_optional_string(user_payload.get("first_name")),
        last_name=_optional_string(user_payload.get("last_name")),
        photo_url=_optional_string(user_payload.get("photo_url")),
        language_code=_optional_string(user_payload.get("language_code")),
        is_premium=_optional_bool(user_payload.get("is_premium")),
    )


def _optional_string(value: Any) -> str | None:
    """normalize optional string"""
    return value if isinstance(value, str) and value else None


def _optional_bool(value: Any) -> bool | None:
    """normalize optional bool"""
    return value if isinstance(value, bool) else None
