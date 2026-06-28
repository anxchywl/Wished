"""DNS-shop product metadata extractor"""

import logging
import re
from urllib.parse import urlparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import DnsParser

logger = logging.getLogger(__name__)

# /product/{hex-id}/{slug}/  — slug may start with a leading number like "238-monitor-..."
_PATH_RE = re.compile(r"/product/[^/]+/([^/]+)/?$", re.IGNORECASE)
_LEADING_NUM_RE = re.compile(r"^\d+-")


def _title_from_url(url: str) -> str | None:
    m = _PATH_RE.search(urlparse(url).path)
    if not m:
        return None
    slug = _LEADING_NUM_RE.sub("", m.group(1)).replace("-", " ").strip()
    return slug[:1].upper() + slug[1:] if slug else None


class DnsExtractor:
    async def extract(
        self, url: str, hostname: str, client: httpx.AsyncClient
    ) -> LinkPreviewResponse:
        html = ""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("DNS fetch failed for %s: %s", url, exc)

        data = DnsParser().parse(html, url, hostname)
        title = data.title or _title_from_url(url)
        price = str(data.price) if data.price is not None else None
        return LinkPreviewResponse(
            title=title,
            description=data.description,
            image_url=data.image_url,
            price=price,
            currency=data.currency if price else None,
            source="dns",
        )
