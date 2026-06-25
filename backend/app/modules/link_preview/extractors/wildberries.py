"""Wildberries product metadata extractor

Strategy:
1. WB CDN card.json  — public, globally accessible, has title + brand + description
2. WB card API       — has price; geo-blocked on non-RU IPs (returns 404)
3. Page HTML fallback
"""

import asyncio
import logging
import re
from decimal import Decimal, InvalidOperation

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import WildberriesParser, truncate_to_sentences

logger = logging.getLogger(__name__)

_WB_CDN_TIMEOUT = 6.0
_WB_CARD_API_TIMEOUT = 5.0


def _wb_basket(article_id: int) -> str:
    """compute the CDN basket number for a WB article ID (best guess; probe if it returns 404)"""
    vol = article_id // 100000
    thresholds = [
        143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601,
        1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269, 3485,
        3701, 3917, 4133, 4349, 4565, 4781, 4997, 5213, 5429, 5645,
        5861, 6077, 6293, 6509, 6725, 6941, 7157, 7373, 7589, 7805,
        8021, 8237, 8453, 8669, 8885, 9101, 9317, 9533, 9749, 9965,
    ]
    return next((f"{i + 1:02d}" for i, t in enumerate(thresholds) if vol < t), "51")


async def _probe_wb_cdn_card(article_id: int, client: httpx.AsyncClient) -> tuple[str, dict] | None:
    """find the CDN basket serving card.json and return (basket, parsed_card_data).

    Uses GET (not HEAD) because wbbasket.ru CDN rejects HEAD from non-RU IPs.
    Tries the computed basket first; probes ±10 neighbors in parallel on miss.
    """
    vol = article_id // 100000
    part = article_id // 1000
    primary = _wb_basket(article_id)
    primary_int = int(primary)

    async def _try(basket_num: int) -> tuple[str, dict] | None:
        b = f"{basket_num:02d}"
        url = f"https://basket-{b}.wbbasket.ru/vol{vol}/part{part}/{article_id}/info/ru/card.json"
        try:
            r = await client.get(url, timeout=_WB_CDN_TIMEOUT)
            if r.status_code == 200:
                return b, r.json()
        except Exception:
            pass
        return None

    # fast path: primary basket
    result = await _try(primary_int)
    if result:
        return result

    # slow path: probe ±10 neighbors in parallel
    neighbors = [n for n in range(max(1, primary_int - 10), primary_int + 11) if n != primary_int]
    results = await asyncio.gather(*[_try(n) for n in neighbors])
    return next((r for r in results if r), None)


def _wb_image_url(article_id: int, basket: str | None = None) -> str:
    vol = article_id // 100000
    part = article_id // 1000
    b = basket or _wb_basket(article_id)
    return f"https://basket-{b}.wbbasket.ru/vol{vol}/part{part}/{article_id}/images/big/1.webp"


def _parse_wb_cdn_card(data: dict) -> dict:
    """extract title and description from a parsed card.json dict"""
    brand = (data.get("selling", {}).get("brand_name") or "").strip()
    name = (data.get("imt_name") or "").strip()
    title = f"{brand} {name}".strip() if brand and name else (brand or name or None)
    raw_desc = (data.get("description") or "").strip()
    description = truncate_to_sentences(raw_desc, 3) if raw_desc else None
    return {"title": title, "description": description}


async def _fetch_wb_cdn_price(article_id: int, basket: str, client: httpx.AsyncClient) -> tuple[str, str] | None:
    """fetch current price from WB CDN price-history — works from any IP, price in kopecks.

    Returns (price_str, currency) preferring KZT when available.
    """
    vol = article_id // 100000
    part = article_id // 1000
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/info/price-history.json"
    try:
        resp = await client.get(url, timeout=_WB_CDN_TIMEOUT)
        resp.raise_for_status()
        entries = resp.json()
        if not entries:
            return None
        latest = entries[-1].get("price") or {}
        if latest.get("KZT"):
            return str(Decimal(latest["KZT"]) / 100), "KZT"
        if latest.get("RUB"):
            return str(Decimal(latest["RUB"]) / 100), "RUB"
    except Exception as exc:
        logger.debug("WB CDN price-history failed for %s: %s", article_id, exc)
    return None


async def _fetch_wb_card_api(article_id: int, client: httpx.AsyncClient) -> dict | None:
    """fetch sale price from WB card API — geo-blocked on non-RU IPs, but preferred when available"""
    try:
        api_url = (
            f"https://card.wb.ru/cards/v2/detail"
            f"?appType=1&curr=rub&dest=-1257786&nm={article_id}"
        )
        headers = {
            "Referer": "https://www.wildberries.ru/",
            "Origin": "https://www.wildberries.ru",
            "Accept": "application/json, text/plain, */*",
        }
        resp = await client.get(api_url, headers=headers, timeout=_WB_CARD_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        products = (data.get("data") or {}).get("products") or []
        if not products:
            return None

        product = products[0]
        price: str | None = None
        sale_price_u = product.get("salePriceU") or product.get("priceU")
        if sale_price_u:
            try:
                price = str(Decimal(sale_price_u) / 100)
            except (InvalidOperation, TypeError):
                pass

        return {"price": price}
    except Exception as exc:
        logger.debug("WB card API failed for article %s: %s", article_id, exc)
        return None


class WildberriesExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        match = re.search(r"/catalog/(\d+)/", url)
        # short links (wb.ru/s/...) don't contain the catalog ID — follow the redirect
        # to discover the canonical wildberries.ru/catalog/... URL first
        if not match:
            try:
                resp = await client.get(url)
                canonical = str(resp.url)
                match = re.search(r"/catalog/(\d+)/", canonical)
                if match:
                    url = canonical
                    hostname = "wildberries.ru"
            except Exception as exc:
                logger.debug("WB short-link redirect failed for %s: %s", url, exc)
        if not match:
            return LinkPreviewResponse(title=None, description=None, image_url=None, price=None, currency=None, source="wildberries")

        article_id = int(match.group(1))
        currency = "KZT" if "wildberries.kz" in hostname else "RUB"

        # probe CDN for basket + card data, and hit card API in parallel
        probe_result, api_data = await asyncio.gather(
            _probe_wb_cdn_card(article_id, client),
            _fetch_wb_card_api(article_id, client),
        )

        if probe_result:
            basket, raw_card = probe_result
            cdn_data = _parse_wb_cdn_card(raw_card)
            cdn_price_result = await _fetch_wb_cdn_price(article_id, basket, client)
        else:
            basket, cdn_data, cdn_price_result = None, None, None

        image_url = _wb_image_url(article_id, basket)

        title = (cdn_data or {}).get("title")
        description = (cdn_data or {}).get("description")

        # prefer card API sale price; fall back to CDN list price
        # CDN price-history also carries the correct currency (KZT preferred over RUB)
        api_price = (api_data or {}).get("price")
        if api_price:
            price = api_price
            # keep hostname-derived currency for card API prices
        elif cdn_price_result:
            price, currency = cdn_price_result
        else:
            price = None

        if title:
            return LinkPreviewResponse(
                title=title,
                description=description,
                image_url=image_url,
                price=price,
                currency=currency if price else None,
                source="wildberries",
            )

        # fallback: fetch page HTML
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = WildberriesParser().parse(resp.text, url, hostname)
            html_price = str(data.price) if data.price is not None else price
            return LinkPreviewResponse(
                title=data.title,
                description=data.description,
                image_url=data.image_url or image_url,
                price=html_price,
                currency=currency if html_price else None,
                source="wildberries",
            )
        except Exception as exc:
            logger.debug("WB page fetch failed for %s: %s", url, exc)

        return LinkPreviewResponse(title=None, description=description, image_url=image_url, price=price, currency=currency if price else None, source="wildberries")
