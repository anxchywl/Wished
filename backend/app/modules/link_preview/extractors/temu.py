"""Temu product metadata extractor

Temu serves a JS bot-challenge to server-side requests, so HTTP scraping is
unreliable. However, both full product URLs and share.temu.com short links
carry the product image and enough info to extract a title without any page
fetch:

Full URL:
  https://www.temu.com/{locale}/{slug}-g-{id}.html?top_gallery_url={img_url}&...

Share link (307 → full URL with same params):
  https://share.temu.com/{token}  →  307 →  https://www.temu.com/...?top_gallery_url=...

httpx follow_redirects=True resolves the short link before we see it, so both
cases are handled identically: inspect the final URL for params + slug.
"""

import logging
import re
from urllib.parse import urlparse, parse_qs, unquote

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse

logger = logging.getLogger(__name__)

# Matches /{locale}/{slug}-g-{numeric_id}.html  or  /goods.html?goods_id=...
_SLUG_RE = re.compile(r"/[^/]+/(.+)-g-\d+\.html", re.IGNORECASE)


def _title_from_url(url: str) -> str | None:
    """derive human-readable title from Temu product URL slug"""
    parsed = urlparse(url)

    # /kz-en/1pc-olive-oil-sprayer-g-12345.html  →  "1pc Olive Oil Sprayer"
    m = _SLUG_RE.search(parsed.path)
    if m:
        slug = m.group(1)
        # remove leading {count}pc- style prefixes if desired, but keep as-is
        title = slug.replace("-", " ").strip()
        # capitalise first letter only (product names are already descriptive)
        return title[:1].upper() + title[1:] if title else None
    return None


def _image_from_url(url: str) -> str | None:
    """extract product image URL from Temu URL query parameters"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for param in ("top_gallery_url", "share_img"):
        values = qs.get(param)
        if values:
            img = unquote(values[0])
            if img.startswith("http"):
                return img
    return None


def _title_from_og(html: str) -> str | None:
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        return m.group(1).strip() or None
    m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']', html, re.IGNORECASE)
    if m:
        return m.group(1).strip() or None
    return None


class TemuExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        final_url = url
        html = ""
        try:
            resp = await client.get(url)
            final_url = str(resp.url)
            html = resp.text
        except Exception as exc:
            logger.debug("Temu fetch failed for %s: %s", url, exc)

        title = _title_from_url(final_url) or _title_from_url(url) or _title_from_og(html)
        image_url = _image_from_url(final_url) or _image_from_url(url)

        return LinkPreviewResponse(
            title=title,
            description=None,
            image_url=image_url,
            price=None,
            currency=None,
            source="temu",
        )
