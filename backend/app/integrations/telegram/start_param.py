"""decode Telegram Mini App start params.

Mirrors the frontend encoder in frontend/src/lib/telegram/start-param.ts so the
inline-query handler can recover the wishlist id and share token from a deep link
start param without trusting any other inline-query data.

"wb_" = compact binary format (two raw UUIDs + optional share token).
"wl_" = legacy base64(JSON) links.
"""

import base64
import json
from dataclasses import dataclass
from uuid import UUID

WISHLIST_BINARY_PREFIX = "wb_"
WISHLIST_PREFIX = "wl_"
# 16 bytes per UUID, 2 UUIDs -> 32 bytes -> 43 base64url chars (no padding)
_BINARY_UUIDS_LENGTH = 43


@dataclass(frozen=True)
class WishlistStartParam:
    user_id: UUID
    wishlist_id: UUID
    share_token: str | None = None


def _base64url_to_bytes(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)


def decode_wishlist_start_param(value: str) -> WishlistStartParam | None:
    """recover wishlist id + share token from a start param; None if malformed"""
    if not value:
        return None

    if value.startswith(WISHLIST_BINARY_PREFIX):
        try:
            body = value[len(WISHLIST_BINARY_PREFIX) :]
            blob = _base64url_to_bytes(body[:_BINARY_UUIDS_LENGTH])
            if len(blob) < 32:
                return None
            share_token = body[_BINARY_UUIDS_LENGTH:] or None
            return WishlistStartParam(
                user_id=UUID(bytes=blob[:16]),
                wishlist_id=UUID(bytes=blob[16:32]),
                share_token=share_token,
            )
        except (ValueError, TypeError):
            return None

    if value.startswith(WISHLIST_PREFIX):
        try:
            decoded = _base64url_to_bytes(value[len(WISHLIST_PREFIX) :]).decode()
            parsed = json.loads(decoded)
            if not isinstance(parsed, dict):
                return None
            wishlist_id = parsed.get("wishlistId")
            user_id = parsed.get("userId")
            if not isinstance(wishlist_id, str) or not isinstance(user_id, str):
                return None
            share_token = parsed.get("shareToken")
            return WishlistStartParam(
                user_id=UUID(user_id),
                wishlist_id=UUID(wishlist_id),
                share_token=share_token if isinstance(share_token, str) and share_token else None,
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    return None
