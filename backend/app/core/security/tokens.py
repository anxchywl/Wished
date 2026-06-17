import hashlib
import secrets


def generate_refresh_token() -> str:
    """generate refresh token"""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """hash token value"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
