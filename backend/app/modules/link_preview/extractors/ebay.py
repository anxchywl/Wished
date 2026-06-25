"""eBay product metadata extractor

eBay blocks datacenter IPs entirely — this extractor requires MARKETPLACE_PROXY_URL.
Without a proxy the response is an error page.

Extraction chain (tries each, uses first success):
1. JSON-LD <script type="application/ld+json"> — has name, image, offers.price
2. OpenGraph meta tags — og:title, og:image
3. <title> tag — last resort, title only
"""

import json
import logging
import re

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import _meta_content, _title_text

logger = logging.getLogger(__name__)

_LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)


def _parse_json_ld(html: str) -> dict:
    for m in _LD_RE.finditer(html):
        try:
            d = json.loads(m.group(1))
            if d.get("@type") in ("Product", "Offer") or d.get("name"):
                return d
        except Exception:
            continue
    return {}


class EbayExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        html: str | None = None
        try:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 5000:
                html = resp.text
            else:
                logger.debug("eBay fetch returned %s (%d bytes) for %s", resp.status_code, len(resp.text), url)
        except Exception as exc:
            logger.debug("eBay page fetch failed for %s: %s", url, exc)

        if not html:
            return LinkPreviewResponse(
                title=None, description=None, image_url=None,
                price=None, currency=None, source="ebay",
            )

        # 1. JSON-LD
        ld = _parse_json_ld(html)
        title: str | None = ld.get("name")
        image_url: str | None = None
        img = ld.get("image")
        if isinstance(img, list):
            image_url = img[0] if img else None
        elif isinstance(img, str):
            image_url = img
        price: str | None = None
        currency: str | None = None
        offers = ld.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if offers:
            p = offers.get("price") or offers.get("lowPrice")
            price = str(p) if p is not None else None
            currency = offers.get("priceCurrency")

        # 2. OG tags fallback
        if not title:
            title = _meta_content(html, "og:title")
        if not image_url:
            image_url = _meta_content(html, "og:image") or _meta_content(html, "og:image:url")

        # 3. <title> tag fallback
        if not title:
            title = _title_text(html)
            if title:
                title = re.sub(r"\s*[|\-]\s*eBay.*$", "", title, flags=re.IGNORECASE).strip()

        # cap at 7 words — eBay titles are notoriously long
        if title:
            words = title.split()
            if len(words) > 7:
                title = " ".join(words[:7])

        return LinkPreviewResponse(
            title=title,
            description=None,
            image_url=image_url,
            price=price,
            currency=currency if price else None,
            source="ebay",
        )
