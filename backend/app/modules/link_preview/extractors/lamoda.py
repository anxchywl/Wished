"""Lamoda product metadata extractor"""

import logging
import re
from urllib.parse import urlparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import LamodaParser

logger = logging.getLogger(__name__)

# /p/{code}/{category}-{brand}-{product-name}/
_PATH_RE = re.compile(r"/p/[^/]+/([^/]+)/?$", re.IGNORECASE)


def _title_from_url(url: str) -> str | None:
    m = _PATH_RE.search(urlparse(url).path)
    if not m:
        return None
    # segment looks like: "home_accs-smartimage-shkatulka"
    # split on first "-" to drop the category prefix (may contain underscores)
    segment = m.group(1)
    # find position after first word-group (category ends at first "-")
    dash_idx = segment.find("-")
    if dash_idx != -1:
        segment = segment[dash_idx + 1:]
    title = segment.replace("-", " ").strip()
    return title[:1].upper() + title[1:] if title else None


class LamodaExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        html = ""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("Lamoda fetch failed for %s: %s", url, exc)

        data = LamodaParser().parse(html, url, hostname)
        title = data.title or _title_from_url(url)
        price = str(data.price) if data.price is not None else None
        return LinkPreviewResponse(
            title=title,
            description=data.description,
            image_url=data.image_url,
            price=price,
            currency=data.currency if price else None,
            source="lamoda",
        )
