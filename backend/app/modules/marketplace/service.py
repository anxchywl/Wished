"""marketplace product import service

Client-assisted architecture: the user's browser fetches the product page
(residential IP, no bot-blocking) and extracts structured metadata.
The backend receives the extracted data, validates it, processes the image
through the existing media pipeline, and returns the normalized result.

For Wildberries, the backend also calls the public WB card API as a server-side
enhancement — this API is accessible from datacenter IPs without restrictions.
"""

import asyncio
import ipaddress
import json
import logging
import re
import socket
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import Settings
from app.integrations.minio import get_presigned_url, upload_object
from app.modules.marketplace.schemas import ImportClientPayload, ImportResult

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 10.0
_MAX_IMAGE_BYTES = 15 * 1024 * 1024
_CACHE_TTL = 3600

ALLOWED_HOSTS: frozenset[str] = frozenset({
    "kaspi.kz",
    "www.kaspi.kz",
    "wildberries.ru",
    "www.wildberries.ru",
    "wildberries.kz",
    "www.wildberries.kz",
    "ozon.ru",
    "www.ozon.ru",
    "ozon.kz",
    "www.ozon.kz",
})

_MARKETPLACE_BY_HOST: dict[str, str] = {
    "kaspi.kz": "kaspi",
    "www.kaspi.kz": "kaspi",
    "wildberries.ru": "wildberries",
    "www.wildberries.ru": "wildberries",
    "wildberries.kz": "wildberries",
    "www.wildberries.kz": "wildberries",
    "ozon.ru": "ozon",
    "www.ozon.ru": "ozon",
    "ozon.kz": "ozon",
    "www.ozon.kz": "ozon",
}

_WB_HOSTS: frozenset[str] = frozenset({
    "wildberries.ru", "www.wildberries.ru",
    "wildberries.kz", "www.wildberries.kz",
})

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_import_url(url: str) -> tuple[str, str]:
    """validate URL scheme and hostname allowlist — returns (url, hostname)"""
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid URL") from exc

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="URL must use http or https scheme",
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid URL")

    if hostname not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="unsupported marketplace",
        )

    return url, hostname


async def _check_host_not_private(hostname: str) -> None:
    """resolve hostname and reject private/loopback/reserved IPs (SSRF protection)"""
    try:
        results = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="could not resolve hostname",
        ) from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="requests to private or reserved addresses are not allowed",
                )
        except ValueError:
            continue


async def _check_import_rate_limit(redis: Redis, user_id: UUID, settings: Settings) -> None:
    uid = str(user_id)
    per_minute_key = f"marketplace:import:min:{uid}"
    per_hour_key = f"marketplace:import:hr:{uid}"

    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(per_minute_key)
        pipe.expire(per_minute_key, 60)
        pipe.incr(per_hour_key)
        pipe.expire(per_hour_key, 3600)
        results = await pipe.execute()

    if results[0] > settings.marketplace_import_rate_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="import rate limit exceeded — try again in a minute",
        )
    if results[2] > settings.marketplace_import_rate_per_hour:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="import rate limit exceeded — try again later",
        )


def _wb_image_url(article_id: int) -> str:
    """compute Wildberries CDN image URL from article ID"""
    vol = article_id // 100000
    part = article_id // 1000
    thresholds = [
        143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601,
        1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269,
    ]
    basket = next((f"{i + 1:02d}" for i, t in enumerate(thresholds) if vol < t), "20")
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/images/big/1.webp"


def _wb_api_cache_key(article_id: int) -> str:
    return f"marketplace:wb_card:{article_id}"


async def _fetch_wb_card_api(url: str, redis: Redis | None = None) -> dict | None:
    """fetch product data from Wildberries public JSON card API

    This API is accessible from datacenter IPs without bot-blocking,
    unlike the web page itself.
    """
    match = re.search(r"/catalog/(\d+)/", url)
    if not match:
        return None
    article_id = int(match.group(1))

    if redis is not None:
        cache_key = _wb_api_cache_key(article_id)
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        api_url = (
            f"https://card.wb.ru/cards/v2/detail"
            f"?appType=1&curr=rub&dest=-1257786&nm={article_id}"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": "https://www.wildberries.ru/",
            "Origin": "https://www.wildberries.ru",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        products = (data.get("data") or {}).get("products") or []
        if not products:
            return None

        product = products[0]
        brand = (product.get("brand") or "").strip()
        name = (product.get("name") or "").strip()
        title = f"{brand} {name}".strip() if brand and name else (brand or name or None)

        sale_price_u = product.get("salePriceU") or product.get("priceU")
        price: str | None = None
        if sale_price_u:
            try:
                price = str(Decimal(sale_price_u) / 100)
            except (InvalidOperation, TypeError):
                pass

        result = {
            "title": title,
            "price": price,
            "currency": "RUB" if price else None,
            "image_url": _wb_image_url(article_id),
        }
        if redis is not None:
            try:
                await redis.setex(_wb_api_cache_key(article_id), _CACHE_TTL, json.dumps(result))
            except Exception:
                pass
        return result
    except Exception as exc:
        logger.warning("WB card API failed for %s: %s", url, exc)
        return None


async def _download_and_process_image(
    image_url: str,
    user_id: UUID,
    settings: Settings,
) -> tuple[UUID, str, str, str, int] | None:
    """download, process through media pipeline, upload to MinIO temp location"""
    from app.modules.media.processing import process_image

    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            max_redirects=4,
        ) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            content = response.content
    except Exception as exc:
        logger.warning("marketplace image download failed: %s", exc)
        return None

    if not content or len(content) > _MAX_IMAGE_BYTES:
        return None

    try:
        thumbnail_bytes, medium_bytes = process_image(content)
    except ValueError as exc:
        logger.warning("marketplace image processing failed: %s", exc)
        return None

    image_uuid = uuid4()
    bucket = settings.minio_media_bucket
    medium_key = f"marketplace-temp/{user_id}/{image_uuid}-m"
    thumb_key = f"marketplace-temp/{user_id}/{image_uuid}-t"

    try:
        upload_object(bucket, medium_key, medium_bytes, "image/webp")
        upload_object(bucket, thumb_key, thumbnail_bytes, "image/webp")
    except Exception as exc:
        logger.warning("marketplace image upload failed: %s", exc)
        return None

    return image_uuid, medium_key, thumb_key, medium_key, len(medium_bytes)


def _image_meta_cache_key(user_id: UUID, image_uuid: UUID) -> str:
    return f"marketplace_img:{user_id}:{image_uuid}"


async def _increment_stat(redis: Redis, key: str) -> None:
    try:
        await redis.incr(key)
    except Exception:
        pass


async def import_product(
    payload: ImportClientPayload,
    url: str,
    hostname: str,
    user_id: UUID,
    settings: Settings,
    redis: Redis,
) -> ImportResult:
    """validate client-extracted product data, enhance with WB card API, process image"""
    await _check_import_rate_limit(redis, user_id, settings)
    await _increment_stat(redis, "marketplace_stats:total")

    title = payload.title or None
    description = payload.description or None
    price_str = payload.price or None
    currency = payload.currency or None
    image_url = payload.image_url or None
    marketplace = payload.marketplace or _MARKETPLACE_BY_HOST.get(hostname)

    # For Wildberries: try card API for title/price, always derive image URL from article ID
    if hostname in _WB_HOSTS:
        match = re.search(r"/catalog/(\d+)/", url)
        if match and not image_url:
            image_url = _wb_image_url(int(match.group(1)))
        if not title:
            wb_data = await _fetch_wb_card_api(url, redis=redis)
            if wb_data:
                title = title or wb_data.get("title")
                price_str = price_str or wb_data.get("price")
                currency = currency or wb_data.get("currency")
                image_url = image_url or wb_data.get("image_url")

    # SSRF check on image URL before downloading
    if image_url:
        try:
            parsed_img = urlparse(image_url)
            if parsed_img.scheme not in ("http", "https"):
                image_url = None
            elif parsed_img.hostname:
                await _check_host_not_private(parsed_img.hostname)
        except HTTPException:
            image_url = None
        except Exception:
            image_url = None

    # Download + process image through existing media pipeline
    pending_image_id: UUID | None = None
    pending_image_thumbnail_url: str | None = None

    if image_url:
        image_result = await _download_and_process_image(image_url, user_id, settings)
        if image_result is not None:
            img_uuid, full_key, thumb_key, medium_key, size_bytes = image_result
            pending_image_id = img_uuid
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
                    _CACHE_TTL,
                    json.dumps(img_meta),
                )
            except Exception:
                pass
            try:
                pending_image_thumbnail_url = get_presigned_url(settings.minio_media_bucket, thumb_key)
            except Exception:
                pending_image_thumbnail_url = None

    await _increment_stat(redis, "marketplace_stats:success")

    price_decimal: Decimal | None = None
    if price_str is not None:
        try:
            price_decimal = Decimal(price_str)
        except (InvalidOperation, ValueError):
            pass

    return ImportResult(
        title=title,
        description=description,
        price=price_decimal,
        currency=currency,
        marketplace=marketplace,
        original_url=url,
        pending_image_id=pending_image_id,
        pending_image_thumbnail_url=pending_image_thumbnail_url,
    )


async def get_pending_image_meta(
    redis: Redis,
    user_id: UUID,
    pending_image_id: UUID,
) -> dict | None:
    """retrieve temp image metadata stored during import"""
    key = _image_meta_cache_key(user_id, pending_image_id)
    raw = await redis.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
