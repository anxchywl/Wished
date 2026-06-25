"""DNS-shop product metadata extractor"""

import logging

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import DnsParser

logger = logging.getLogger(__name__)


class DnsExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("DNS fetch failed for %s: %s", url, exc)
            return LinkPreviewResponse(
                title=None, description=None, image_url=None, price=None, currency=None, source="dns"
            )

        data = DnsParser().parse(html, url, hostname)
        price = str(data.price) if data.price is not None else None
        return LinkPreviewResponse(
            title=data.title,
            description=data.description,
            image_url=data.image_url,
            price=price,
            currency=data.currency if price else None,
            source="dns",
        )
