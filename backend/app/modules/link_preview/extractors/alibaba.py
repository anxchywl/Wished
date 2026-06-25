"""Alibaba / AliExpress product metadata extractor

Alibaba serves a CAPTCHA/bot-protection page to datacenter IPs, even through
many proxies. Extraction chain:

1. URL-slug title — always available for both alibaba.com and aliexpress.com
2. Page fetch (with proxy) — may succeed if proxy has residential IPs;
   parses og:title, og:image, og:description
3. Fallback to slug title only if page fetch fails or returns challenge page
"""

import logging
import re
from urllib.parse import urlparse

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import _meta_content

logger = logging.getLogger(__name__)

# /product-detail/{slug}_{id}.html  or  /item/{id}.htm  (AliExpress)
_ALIBABA_SLUG_RE = re.compile(r"/product-detail/([^_/]+)_", re.IGNORECASE)
_ALIEXPRESS_ID_RE = re.compile(r"/item/(\d+)\.html", re.IGNORECASE)

# Detect challenge/CAPTCHA pages — they are very small and lack product data
_MIN_PRODUCT_HTML_BYTES = 20_000


def _title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    m = _ALIBABA_SLUG_RE.search(parsed.path)
    if m:
        slug = m.group(1)
        return re.sub(r"\s+", " ", slug.replace("-", " ")).strip().title()
    return None


def _is_challenge_page(html: str) -> bool:
    """detect CAPTCHA / bot-protection pages by small size or known markers"""
    if len(html) < _MIN_PRODUCT_HTML_BYTES:
        return True
    if "punish-component" in html or "awsc.js" in html:
        return True
    return False


class AlibabaExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        slug_title = _title_from_url(url)
        html: str | None = None

        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                text = resp.text
                if not _is_challenge_page(text):
                    html = text
                else:
                    logger.debug("Alibaba returned challenge page for %s (%d bytes)", url, len(text))
        except Exception as exc:
            logger.debug("Alibaba page fetch failed for %s: %s", url, exc)

        if html:
            title = (
                _meta_content(html, "og:title")
                or _meta_content(html, "title")
                or slug_title
            )
            image_url = (
                _meta_content(html, "og:image")
                or _meta_content(html, "og:image:url")
            )
            description = _meta_content(html, "og:description") or _meta_content(html, "description")
            return LinkPreviewResponse(
                title=title,
                description=description,
                image_url=image_url,
                price=None,
                currency=None,
                source="alibaba",
            )

        # challenge page or fetch failed — return title from URL slug
        return LinkPreviewResponse(
            title=slug_title,
            description=None,
            image_url=None,
            price=None,
            currency=None,
            source="alibaba",
        )
