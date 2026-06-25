"""Amazon product metadata extractor

Amazon blocks datacenter IPs with bot detection, so this extractor requires
MARKETPLACE_PROXY_URL to be configured. Without a proxy it will return only
a title derived from the page <title> tag if the request succeeds.

Supported hostnames: amazon.com, amazon.co.uk, amazon.de, amazon.fr, amazon.co.jp,
amazon.ca, amazon.in, amazon.com.au, amazon.com.br, amazon.com.mx, amazon.es, amazon.it,
amazon.nl, amazon.se, amazon.pl, amazon.sg, amazon.ae, amazon.sa, plus www. variants
and short-link domains (a.co, amzn.to, amzn.eu).
"""

import logging
import re
from collections import Counter

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse

logger = logging.getLogger(__name__)

# Amazon CDN image base URL
_CDN = "https://m.media-amazon.com/images/I/"

# Amazon title tag starts with "Amazon.com: " or "Amazon.{tld}: " — strip it
_TITLE_PREFIX_RE = re.compile(r"^Amazon(?:\.\w+)+\s*:\s*", re.IGNORECASE)

# Match image IDs (11-char alphanumeric)
_IMG_ID_RE = re.compile(r"/images/I/([A-Za-z0-9]{11,12})\._")

# Amazon title meta tag
_META_TITLE_RE = re.compile(r'<meta[^>]+name="title"[^>]+content="([^"]+)"', re.IGNORECASE)
_META_TITLE_RE2 = re.compile(r'<meta[^>]+content="([^"]+)"[^>]+name="title"', re.IGNORECASE)

# Price
_PRICE_RE = re.compile(r'"priceAmount"\s*:\s*(\d+(?:\.\d+)?)')
_CURRENCY_RE = re.compile(r'"currencyCode"\s*:\s*"([A-Z]{3})"')

# Span with id=productTitle
_PRODUCT_TITLE_RE = re.compile(r'id="productTitle"[^>]*>(.*?)</span>', re.DOTALL)


def _extract_title(html: str) -> str | None:
    m = _PRODUCT_TITLE_RE.search(html)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if title:
            return title
    for pattern in (_META_TITLE_RE, _META_TITLE_RE2):
        m = pattern.search(html)
        if m:
            title = m.group(1).strip()
            title = _TITLE_PREFIX_RE.sub("", title)
            # strip trailing " - Amazon.com" or ": Electronics" junk
            title = re.sub(r"\s*[-:]?\s*Amazon\.\w+.*$", "", title, flags=re.IGNORECASE).strip()
            if title:
                return title
    return None


def _extract_image(html: str) -> str | None:
    ids = _IMG_ID_RE.findall(html)
    if not ids:
        return None
    # The main product image ID is referenced most frequently
    most_common_id, count = Counter(ids).most_common(1)[0]
    if count < 2:
        return None
    return f"{_CDN}{most_common_id}._SL1500_.jpg"


def _extract_price(html: str) -> tuple[str | None, str | None]:
    pm = _PRICE_RE.search(html)
    cm = _CURRENCY_RE.search(html)
    price = pm.group(1) if pm else None
    currency = cm.group(1) if cm else None
    return price, currency


class AmazonExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        html: str | None = None
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
            else:
                logger.debug("Amazon fetch returned %s for %s", resp.status_code, url)
        except Exception as exc:
            logger.debug("Amazon page fetch failed for %s: %s", url, exc)

        if not html:
            return LinkPreviewResponse(
                title=None, description=None, image_url=None,
                price=None, currency=None, source="amazon",
            )

        title = _extract_title(html)
        image_url = _extract_image(html)
        price, currency = _extract_price(html)

        return LinkPreviewResponse(
            title=title,
            description=None,
            image_url=image_url,
            price=price,
            currency=currency if price else None,
            source="amazon",
        )
