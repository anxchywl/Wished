"""link preview service — server-side metadata extraction from product URLs"""

import asyncio
import hashlib
import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import Settings
from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import truncate_to_sentences

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 512 * 1024  # 512 KB of HTML is enough for metadata
_CACHE_TTL = 86400  # 24 hours
_RATE_LIMIT_WINDOW = 3600  # 1 hour

_WB_HOSTS = frozenset({
    "wildberries.ru", "www.wildberries.ru",
    "wildberries.kz", "www.wildberries.kz",
})
_OZON_HOSTS = frozenset({"ozon.ru", "www.ozon.ru", "ozon.kz", "www.ozon.kz"})
_KASPI_HOSTS = frozenset({"kaspi.kz", "www.kaspi.kz"})

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def validate_preview_url(url: str) -> tuple[str, str]:
    """validate URL scheme and format; returns (normalized_url, hostname)"""
    url = url.strip()
    if len(url) > 2048:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL too long",
        )
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid URL",
        ) from exc

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must use http or https scheme",
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid URL",
        )

    # reject obvious loopback and private hostnames before DNS resolution
    if hostname in ("localhost", "127.0.0.1", "::1"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="requests to private or reserved addresses are not allowed",
        )

    return url, hostname


async def _check_host_not_private(hostname: str) -> None:
    """resolve hostname and reject private/loopback/reserved IPs"""
    try:
        results = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="could not resolve hostname",
        ) from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="requests to private or reserved addresses are not allowed",
                )
        except ValueError:
            continue


def _cache_key(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:32]
    return f"link_preview:{digest}"


async def _get_cached(redis: Redis, url: str) -> LinkPreviewResponse | None:
    try:
        raw = await redis.get(_cache_key(url))
        if raw:
            return LinkPreviewResponse(**json.loads(raw))
    except Exception:
        pass
    return None


async def _set_cached(redis: Redis, url: str, result: LinkPreviewResponse) -> None:
    try:
        await redis.setex(_cache_key(url), _CACHE_TTL, json.dumps(result.model_dump()))
    except Exception:
        pass


async def _check_rate_limit(redis: Redis, user_id: UUID, settings: Settings) -> None:
    key = f"link_preview:rl:{user_id}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _RATE_LIMIT_WINDOW)
        if count > settings.link_preview_rate_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="link preview rate limit exceeded — try again later",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("rate limit check failed: %s", exc)


def _choose_extractor(hostname: str):
    if hostname in _WB_HOSTS:
        from app.modules.link_preview.extractors.wildberries import WildberriesExtractor
        return WildberriesExtractor()
    if hostname in _OZON_HOSTS:
        from app.modules.link_preview.extractors.ozon import OzonExtractor
        return OzonExtractor()
    if hostname in _KASPI_HOSTS:
        from app.modules.link_preview.extractors.kaspi import KaspiExtractor
        return KaspiExtractor()
    from app.modules.link_preview.extractors.generic import GenericExtractor
    return GenericExtractor()


async def fetch_link_preview(
    url: str,
    hostname: str,
    user_id: UUID,
    redis: Redis,
    settings: Settings,
) -> LinkPreviewResponse:
    """extract product metadata from a URL with caching and rate limiting"""
    cached = await _get_cached(redis, url)
    if cached is not None:
        return cached

    await _check_rate_limit(redis, user_id, settings)
    await _check_host_not_private(hostname)

    extractor = _choose_extractor(hostname)

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        headers=headers,
    ) as client:
        result = await extractor.extract(url, hostname, client)

    if result.description:
        result = result.model_copy(update={"description": truncate_to_sentences(result.description, 3)})

    await _set_cached(redis, url, result)
    return result
