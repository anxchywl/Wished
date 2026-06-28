"""MVideo product metadata extractor"""

import logging
import re
from urllib.parse import urlparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import MVideoParser

logger = logging.getLogger(__name__)

# /products/{slug}-{numeric-id}
_SLUG_RE = re.compile(r"/products/(.+?)-(\d+)$", re.IGNORECASE)


def _title_from_url(url: str) -> str | None:
    m = _SLUG_RE.search(urlparse(url).path.rstrip("/"))
    if not m:
        return None
    # double-dashes are word separators in MVideo slugs
    slug = m.group(1).replace("--", " ").replace("-", " ").strip()
    return slug[:1].upper() + slug[1:] if slug else None


class MVideoExtractor:
    async def extract(
        self, url: str, hostname: str, client: httpx.AsyncClient
    ) -> LinkPreviewResponse:
        html = ""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("MVideo fetch failed for %s: %s", url, exc)

        data = MVideoParser().parse(html, url, hostname)
        title = data.title or _title_from_url(url)
        price = str(data.price) if data.price is not None else None
        return LinkPreviewResponse(
            title=title,
            description=data.description,
            image_url=data.image_url,
            price=price,
            currency=data.currency if price else None,
            source="mvideo",
        )
