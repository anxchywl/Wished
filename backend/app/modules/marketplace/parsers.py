"""HTML parsers for marketplace product pages

Strategy:
1. JSON-LD (@type: Product)
2. OpenGraph meta tags
3. Marketplace-specific HTML selectors
"""

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class ProductData:
    title: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    marketplace: str | None = None


def _parse_price(text: str) -> Decimal | None:
    """parse price strings with various locale formats"""
    if not text or not text.strip():
        return None

    digits_and_seps = re.sub(r"[^\d.,]", "", text)

    if not digits_and_seps or not any(c.isdigit() for c in digits_and_seps):
        return None

    has_dot = "." in digits_and_seps
    has_comma = "," in digits_and_seps

    if has_dot and has_comma:
        last_dot = digits_and_seps.rfind(".")
        last_comma = digits_and_seps.rfind(",")
        if last_comma > last_dot:
            # European format: 1.234,56
            normalized = digits_and_seps.replace(".", "").replace(",", ".")
        else:
            # US format: 1,234.56
            normalized = digits_and_seps.replace(",", "")
    elif has_comma:
        parts = digits_and_seps.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # decimal comma: 29,99
            normalized = digits_and_seps.replace(",", ".")
        else:
            # thousands separator: 1,234
            normalized = digits_and_seps.replace(",", "")
    else:
        normalized = digits_and_seps

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _extract_json_ld(html: str) -> dict | None:
    """find first JSON-LD script block with @type: Product"""
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                data = next(
                    (d for d in data if isinstance(d, dict) and d.get("@type") == "Product"),
                    None,
                )
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
        except (json.JSONDecodeError, StopIteration, ValueError):
            continue
    return None


def _meta_content(html: str, prop: str) -> str | None:
    """extract content from <meta property|name="prop"> tag"""
    prop_escaped = re.escape(prop)
    for tag_match in re.finditer(r"<meta\b[^>]*>", html, re.IGNORECASE):
        tag = tag_match.group(0)
        if not re.search(rf'(?:property|name)=["\'](?:{prop_escaped})["\']', tag, re.IGNORECASE):
            continue
        m = re.search(r"""content=['"]([^'"]*)['"]\s*""", tag, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _element_text_by_class(html: str, cls: str) -> str | None:
    """extract text content of first element containing the given CSS class"""
    cls_escaped = re.escape(cls)
    pattern = rf'class=["\'][^"\']*{cls_escaped}[^"\']*["\'][^>]*>(.*?)</'
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return text or None
    return None


def _h1_text(html: str) -> str | None:
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return text or None
    return None


def _title_text(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return text or None
    return None


def _parse_json_ld_into(ld: dict, result: ProductData, default_currency: str) -> None:
    result.title = (ld.get("name") or "").strip() or None
    result.description = (ld.get("description") or "").strip() or None

    img = ld.get("image")
    if isinstance(img, str):
        result.image_url = img
    elif isinstance(img, list) and img:
        result.image_url = img[0]

    offers = ld.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if offers.get("price") is not None:
        result.price = _parse_price(str(offers["price"]))
        if result.price is not None:
            result.currency = (offers.get("priceCurrency") or default_currency).upper()[:3]


def _parse_og_into(html: str, result: ProductData, default_currency: str) -> bool:
    """try to populate result from OpenGraph tags; returns True if og:title found"""
    og_title = _meta_content(html, "og:title")
    if not og_title:
        return False
    result.title = og_title.strip() or result.title
    result.image_url = result.image_url or _meta_content(html, "og:image") or _meta_content(html, "og:image:url")
    og_desc = _meta_content(html, "og:description")
    if og_desc and not result.description:
        result.description = og_desc.strip() or None
    price_str = _meta_content(html, "product:price:amount") or _meta_content(html, "og:price:amount")
    if price_str and result.price is None:
        result.price = _parse_price(price_str)
        if result.price is not None:
            cur = _meta_content(html, "product:price:currency") or _meta_content(html, "og:price:currency")
            result.currency = (cur or default_currency).upper()[:3]
    return True


class KaspiParser:
    def parse(self, html: str, url: str, hostname: str) -> ProductData:
        result = ProductData(marketplace="kaspi")

        ld = _extract_json_ld(html)
        if ld:
            _parse_json_ld_into(ld, result, "KZT")
            if result.title:
                return result

        if _parse_og_into(html, result, "KZT"):
            return result

        result.title = _element_text_by_class(html, "item-card__meta-title") or _h1_text(html)
        price_text = _element_text_by_class(html, "item-card__prices-main")
        if price_text:
            result.price = _parse_price(price_text)
            if result.price is not None:
                result.currency = "KZT"
        return result


class WildberriesParser:
    def parse(self, html: str, url: str, hostname: str) -> ProductData:
        result = ProductData(marketplace="wildberries")

        ld = _extract_json_ld(html)
        if ld:
            _parse_json_ld_into(ld, result, "RUB")
            if result.title:
                return result

        if _parse_og_into(html, result, "RUB"):
            return result

        result.title = _element_text_by_class(html, "product-page__title") or _h1_text(html)
        price_text = _element_text_by_class(html, "price-block__wallet-price")
        if price_text:
            result.price = _parse_price(price_text)
            if result.price is not None:
                result.currency = "RUB"
        return result


def _ozon_image_from_state(html: str) -> str | None:
    """extract first product image URL from Ozon's embedded JS state blob"""
    # ir.ozon.com is Ozon's primary image CDN; URLs appear quoted inside JSON blobs
    m = re.search(
        r'"(https://ir\.ozon\.com/multimedia/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # fallback: cdn*.ozon.ru / cdn*.ozon.kz
    m = re.search(
        r'"(https://cdn\d*\.ozon\.(?:ru|kz)/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
        html,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


class OzonParser:
    def parse(self, html: str, url: str, hostname: str) -> ProductData:
        result = ProductData(marketplace="ozon")

        ld = _extract_json_ld(html)
        if ld:
            _parse_json_ld_into(ld, result, "RUB")
            if result.title:
                if not result.image_url:
                    result.image_url = _ozon_image_from_state(html)
                return result

        if _parse_og_into(html, result, "RUB"):
            if not result.image_url:
                result.image_url = _ozon_image_from_state(html)
            return result

        result.title = _h1_text(html)
        result.image_url = _ozon_image_from_state(html)
        return result


_PARSER_BY_HOST: dict[str, type] = {
    "kaspi.kz": KaspiParser,
    "www.kaspi.kz": KaspiParser,
    "wildberries.ru": WildberriesParser,
    "www.wildberries.ru": WildberriesParser,
    "wildberries.kz": WildberriesParser,
    "www.wildberries.kz": WildberriesParser,
    "ozon.ru": OzonParser,
    "www.ozon.ru": OzonParser,
    "ozon.kz": OzonParser,
    "www.ozon.kz": OzonParser,
}


def get_parser(hostname: str) -> KaspiParser | WildberriesParser | OzonParser | None:
    """return the appropriate HTML parser for the given hostname, or None"""
    cls = _PARSER_BY_HOST.get(hostname)
    return cls() if cls else None
