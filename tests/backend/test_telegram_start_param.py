import base64
from uuid import UUID

from app.integrations.telegram.start_param import decode_wishlist_start_param

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
WISHLIST_ID = UUID("22222222-2222-2222-2222-222222222222")


def _encode_binary(user_id: UUID, wishlist_id: UUID, share_token: str = "") -> str:
    blob = user_id.bytes + wishlist_id.bytes
    body = base64.urlsafe_b64encode(blob).decode().rstrip("=")
    return f"wb_{body}{share_token}"


def test_decode_binary_with_share_token() -> None:
    decoded = decode_wishlist_start_param(_encode_binary(USER_ID, WISHLIST_ID, "abc123"))
    assert decoded is not None
    assert decoded.user_id == USER_ID
    assert decoded.wishlist_id == WISHLIST_ID
    assert decoded.share_token == "abc123"


def test_decode_binary_without_share_token() -> None:
    decoded = decode_wishlist_start_param(_encode_binary(USER_ID, WISHLIST_ID))
    assert decoded is not None
    assert decoded.share_token is None


def test_decode_rejects_garbage() -> None:
    assert decode_wishlist_start_param("garbage") is None
    assert decode_wishlist_start_param("wb_short") is None
    assert decode_wishlist_start_param("") is None
    assert decode_wishlist_start_param("p_max_472") is None
