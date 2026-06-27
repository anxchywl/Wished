"""Kaspi marketplace product metadata extractor"""

import logging
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import KaspiParser

logger = logging.getLogger(__name__)

_EMPTY = LinkPreviewResponse(title=None, description=None, image_url=None, price=None, currency=None, source="kaspi")

# /shop/p/{slug}-{numeric-id}/  — numeric ID is always the last dash-segment
_KASPI_SLUG_RE = re.compile(r"/shop/p/([a-z0-9][a-z0-9-]*?)-(\d{5,})/?", re.IGNORECASE)


def _canonical_kaspi_url(url: str) -> str:
    """strip ?c= city param — Kaspi rate-limits per city code on non-KZ IPs"""
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items() if k != "c"}
    query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=query))


def _title_from_slug(url: str) -> str | None:
    """derive a human-readable title from a Kaspi product URL slug"""
    m = _KASPI_SLUG_RE.search(url)
    if not m:
        return None
    slug = m.group(1)
    return " ".join(word.capitalize() for word in slug.split("-"))


class KaspiExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        fetch_url = _canonical_kaspi_url(url)
        html: str | None = None
        try:
            resp = await client.get(fetch_url)
            # do NOT honour a remote Retry-After sleep — a hostile/throttling server
            # could pin our worker tasks for seconds each (slowloris-style). Treat a
            # 429 as a transient miss and fall back to the URL-slug title below.
            if resp.status_code == 200:
                html = resp.text
            else:
                logger.debug("Kaspi fetch returned %s for %s", resp.status_code, url)
        except Exception as exc:
            logger.debug("Kaspi page fetch failed for %s: %s", url, exc)

        if html:
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

        # rate-limited or fetch failed — extract title from URL slug at minimum
        return LinkPreviewResponse(
            title=_title_from_slug(url),
            description=None,
            image_url=None,
            price=None,
            currency=None,
            source="kaspi",
        )
