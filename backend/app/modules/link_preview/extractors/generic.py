"""Generic website metadata extractor

Extracts product metadata from any public webpage using:
1. OpenGraph meta tags (og:title, og:image, og:description)
2. Fallback: <title> tag
3. Fallback: <meta name="description"> tag
"""

import logging
import re

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import _meta_content, _title_text

logger = logging.getLogger(__name__)


def _first_image(html: str) -> str | None:
    """find first meaningful <img src> in the page body"""
    match = re.search(
        r'<img\b[^>]+\bsrc=["\']?(https?://[^"\'>\s]+)["\']?',
        html,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


class GenericExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("generic page fetch failed for %s: %s", url, exc)
            return LinkPreviewResponse(
                title=None, description=None, image_url=None, price=None, source=None
            )

        title = (
            _meta_content(html, "og:title")
            or _title_text(html)
        )
        image_url = (
            _meta_content(html, "og:image")
            or _meta_content(html, "og:image:url")
            or _first_image(html)
        )
        description = (
            _meta_content(html, "og:description")
            or _meta_content(html, "description")
        )

        return LinkPreviewResponse(
            title=title.strip() if title else None,
            description=description.strip() if description else None,
            image_url=image_url,
            price=None,
            source=None,
        )
