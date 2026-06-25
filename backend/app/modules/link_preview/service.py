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
    "global.wildberries.ru", "www.global.wildberries.ru",
})
_OZON_HOSTS = frozenset({"ozon.ru", "www.ozon.ru", "ozon.kz", "www.ozon.kz"})
_KASPI_HOSTS = frozenset({"kaspi.kz", "www.kaspi.kz", "l.kaspi.kz"})
_AMAZON_HOSTS = frozenset({
    "amazon.com", "www.amazon.com",
    "amazon.co.uk", "www.amazon.co.uk",
    "amazon.de", "www.amazon.de",
    "amazon.fr", "www.amazon.fr",
    "amazon.co.jp", "www.amazon.co.jp",
    "amazon.ca", "www.amazon.ca",
    "amazon.in", "www.amazon.in",
    "amazon.com.au", "www.amazon.com.au",
    "amazon.com.br", "www.amazon.com.br",
    "amazon.com.mx", "www.amazon.com.mx",
    "amazon.es", "www.amazon.es",
    "amazon.it", "www.amazon.it",
    "amazon.nl", "www.amazon.nl",
    "amazon.se", "www.amazon.se",
    "amazon.pl", "www.amazon.pl",
    "amazon.sg", "www.amazon.sg",
    "amazon.ae", "www.amazon.ae",
    "amazon.sa", "www.amazon.sa",
    # short-link domains that redirect to amazon.com product pages
    "a.co", "amzn.to", "amzn.eu",
})
_TEMU_HOSTS = frozenset({
    "temu.com", "www.temu.com",
    "share.temu.com",
})
_EBAY_HOSTS = frozenset({
    "ebay.com", "www.ebay.com",
    "ebay.co.uk", "www.ebay.co.uk",
    "ebay.de", "www.ebay.de",
    "ebay.fr", "www.ebay.fr",
    "ebay.it", "www.ebay.it",
    "ebay.es", "www.ebay.es",
    "ebay.com.au", "www.ebay.com.au",
    "ebay.ca", "www.ebay.ca",
    "ebay.at", "www.ebay.at",
    "ebay.be", "www.ebay.be",
    "ebay.nl", "www.ebay.nl",
    "ebay.pl", "www.ebay.pl",
    "ebay.ie", "www.ebay.ie",
    "ebay.ch", "www.ebay.ch",
    "ebay.in", "www.ebay.in",
    "ebay.sg", "www.ebay.sg",
    "ebay.ph", "www.ebay.ph",
    "ebay.com.my", "www.ebay.com.my",
    "ebay.com.hk", "www.ebay.com.hk",
})
_ALIBABA_HOSTS = frozenset({
    "alibaba.com", "www.alibaba.com",
    "aliexpress.com", "www.aliexpress.com",
    "aliexpress.ru", "www.aliexpress.ru",
    "ru.aliexpress.com",
})
_OLX_HOSTS = frozenset({
    "olx.kz", "www.olx.kz",
    "olx.ru", "www.olx.ru",
    "olx.ua", "www.olx.ua",
    "olx.uz", "www.olx.uz",
    "olx.pl", "www.olx.pl",
    "olx.ro", "www.olx.ro",
    "olx.bg", "www.olx.bg",
    "olx.pt", "www.olx.pt",
    "olx.in", "www.olx.in",
})

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
    if hostname in _AMAZON_HOSTS:
        from app.modules.link_preview.extractors.amazon import AmazonExtractor
        return AmazonExtractor()
    if hostname in _TEMU_HOSTS:
        from app.modules.link_preview.extractors.temu import TemuExtractor
        return TemuExtractor()
    if hostname in _EBAY_HOSTS:
        from app.modules.link_preview.extractors.ebay import EbayExtractor
        return EbayExtractor()
    if hostname in _ALIBABA_HOSTS:
        from app.modules.link_preview.extractors.alibaba import AlibabaExtractor
        return AlibabaExtractor()
    if hostname in _OLX_HOSTS:
        from app.modules.link_preview.extractors.olx import OlxExtractor
        return OlxExtractor()
    from app.modules.link_preview.extractors.generic import GenericExtractor
    return GenericExtractor()


async def store_preview_image(
    image_url: str,
    user_id: UUID,
    redis: Redis,
    settings: Settings,
) -> tuple[str, str | None] | None:
    """download a preview image server-side and store it as a pending marketplace image"""
    import json
    from app.modules.marketplace.service import _download_and_process_image, _image_meta_cache_key
    from app.integrations.minio import get_presigned_url

    parsed = urlparse(image_url)
    if parsed.scheme not in ("http", "https"):
        return None
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None
    await _check_host_not_private(hostname)

    result = await _download_and_process_image(image_url, user_id, settings)
    if result is None:
        return None

    img_uuid, full_key, thumb_key, medium_key, size_bytes = result
    img_meta = {
        "bucket": settings.minio_media_bucket,
        "full_key": full_key,
        "thumb_key": thumb_key,
        "medium_key": medium_key,
        "size_bytes": size_bytes,
    }
    try:
        await redis.setex(
            _image_meta_cache_key(user_id, img_uuid),
            86400,
            json.dumps(img_meta),
        )
    except Exception:
        pass

    try:
        thumbnail_url = get_presigned_url(settings.minio_media_bucket, thumb_key)
    except Exception:
        thumbnail_url = None

    return str(img_uuid), thumbnail_url


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

    _PROXY_HOSTS = _KASPI_HOSTS | _OZON_HOSTS | _AMAZON_HOSTS | _EBAY_HOSTS | _ALIBABA_HOSTS
    proxy = settings.marketplace_proxy_url if hostname in _PROXY_HOSTS and settings.marketplace_proxy_url else None

    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        headers=headers,
        proxy=proxy or None,
    ) as client:
        result = await extractor.extract(url, hostname, client)

    if result.description:
        result = result.model_copy(update={"description": truncate_to_sentences(result.description, 3)})

    # only cache successful extractions — don't lock out URLs that failed due to rate limits or transient errors
    if result.title or result.image_url or result.price:
        await _set_cached(redis, url, result)
    return result
