"""OLX classifieds metadata extractor (olx.kz, olx.ru, olx.ua, olx.uz, olx.pl, etc.)

OLX serves regular HTML with OpenGraph meta tags — no bot protection.
Extraction chain:
1. og:title  — listing title
2. og:image  — listing photo
3. og:description / meta description  — may contain price at start: "470 тг.:"
"""

import logging
import re

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import _meta_content

logger = logging.getLogger(__name__)

# "470 тг.:" / "1 200 USD:" / "5,000 KZT -" at the start of the description
_PRICE_RE = re.compile(
    r"^([\d\s ,.]+)\s*(тг|тенге|KZT|₸|руб|RUB|₽|USD|\$|EUR|€|PLN|zł|UAH|₴|UZS|сум)\b",
    re.IGNORECASE | re.UNICODE,
)
# normalise non-breaking space and thin space
_SPACE_NORM = re.compile(r"[\s  ]+")

_CURRENCY_MAP = {
    "тг": "KZT",
    "тенге": "KZT",
    "kzt": "KZT",
    "₸": "KZT",
    "руб": "RUB",
    "rub": "RUB",
    "₽": "RUB",
    "usd": "USD",
    "$": "USD",
    "eur": "EUR",
    "€": "EUR",
    "pln": "PLN",
    "zł": "PLN",
    "uah": "UAH",
    "₴": "UAH",
    "uzs": "UZS",
    "сум": "UZS",
}


def _parse_price(description: str) -> tuple[str | None, str | None]:
    """extract price and currency from the beginning of an OLX description"""
    text = description.strip()
    m = _PRICE_RE.match(text)
    if not m:
        return None, None
    raw_price = _SPACE_NORM.sub("", m.group(1)).replace(",", ".")
    raw_currency = m.group(2).strip().lower()
    price = raw_price if raw_price.replace(".", "").isdigit() else None
    currency = _CURRENCY_MAP.get(raw_currency)
    return price, currency


class OlxExtractor:
    async def extract(
        self, url: str, hostname: str, client: httpx.AsyncClient
    ) -> LinkPreviewResponse:
        html: str | None = None
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
            else:
                logger.debug("OLX fetch returned %s for %s", resp.status_code, url)
        except Exception as exc:
            logger.debug("OLX page fetch failed for %s: %s", url, exc)

        if not html:
            return LinkPreviewResponse(
                title=None,
                description=None,
                image_url=None,
                price=None,
                currency=None,
                source="olx",
            )

        title = _meta_content(html, "og:title")
        image_url = _meta_content(html, "og:image") or _meta_content(html, "og:image:url")
        raw_desc = _meta_content(html, "og:description") or _meta_content(html, "description") or ""

        price, currency = _parse_price(raw_desc)

        # strip price prefix from description before storing it
        if price and raw_desc:
            clean_desc = re.sub(r"^[\d\s ,.]+\s*\S+\.?\s*[:\-]\s*", "", raw_desc).strip()
        else:
            clean_desc = raw_desc.strip()

        return LinkPreviewResponse(
            title=title,
            description=clean_desc or None,
            image_url=image_url,
            price=price,
            currency=currency,
            source="olx",
        )
