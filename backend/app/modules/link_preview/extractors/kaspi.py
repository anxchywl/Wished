"""Kaspi marketplace product metadata extractor"""

import asyncio
import logging
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import KaspiParser

logger = logging.getLogger(__name__)

_EMPTY = LinkPreviewResponse(title=None, description=None, image_url=None, price=None, currency=None, source="kaspi")


def _canonical_kaspi_url(url: str) -> str:
    """strip ?c= city param — Kaspi rate-limits per city code on non-KZ IPs"""
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items() if k != "c"}
    query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=query))


class KaspiExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        fetch_url = _canonical_kaspi_url(url)
        try:
            resp = await client.get(fetch_url)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "3"))
                await asyncio.sleep(min(retry_after, 5))
                resp = await client.get(fetch_url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("Kaspi page fetch failed for %s: %s", url, exc)
            return _EMPTY

        parser = KaspiParser()
        data = parser.parse(html, url, hostname)
        price = str(data.price) if data.price is not None else None
        return LinkPreviewResponse(
            title=data.title,
            description=data.description,
            image_url=data.image_url,
            price=price,
            currency=data.currency if price else None,
            source="kaspi",
        )
