"""Ozon product metadata extractor

Ozon short URLs (ozon.kz/t/...) serve a lightweight teaser page with OG tags.
Direct product URLs (ozon.kz/product/slug-ID/) hit Ozon's antibot and return 403.
For those we fall back to extracting the product name from the URL slug.
"""

import logging
import re

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import OzonParser

logger = logging.getLogger(__name__)

_PRODUCT_SLUG_RE = re.compile(r"/product/([a-z0-9][a-z0-9-]*?)-(\d{5,})/?", re.IGNORECASE)


def _title_from_slug(url: str) -> str | None:
    """derive a human-readable title from an Ozon product URL slug"""
    m = _PRODUCT_SLUG_RE.search(url)
    if not m:
        return None
    slug = m.group(1)  # e.g. "sabo-sabrosso-bear"
    return " ".join(word.capitalize() for word in slug.split("-"))


class OzonExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        html: str | None = None
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            if "Antibot Challenge" not in resp.text:
                html = resp.text
        except Exception as exc:
            logger.debug("Ozon page fetch failed for %s: %s", url, exc)

        if html:
            parser = OzonParser()
            data = parser.parse(html, url, hostname)
            return LinkPreviewResponse(
                title=data.title,
                description=data.description,
                image_url=data.image_url,
                price=str(data.price) if data.price is not None else None,
                source="ozon",
            )

        # antibot or fetch failure — extract what we can from the URL itself
        return LinkPreviewResponse(
            title=_title_from_slug(url),
            description=None,
            image_url=None,
            price=None,
            source="ozon",
        )
