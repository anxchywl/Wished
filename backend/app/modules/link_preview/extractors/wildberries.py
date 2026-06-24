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
    vol = article_id // 100000
    thresholds = [
        143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601,
        1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269,
    ]
    return next((f"{i + 1:02d}" for i, t in enumerate(thresholds) if vol < t), "20")


def _wb_image_url(article_id: int) -> str:
    vol = article_id // 100000
    part = article_id // 1000
    basket = _wb_basket(article_id)
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/images/big/1.webp"


async def _fetch_wb_cdn_card(article_id: int, client: httpx.AsyncClient) -> dict | None:
    """fetch product info from WB's public CDN JSON — works from any IP"""
    vol = article_id // 100000
    part = article_id // 1000
    basket = _wb_basket(article_id)
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/info/ru/card.json"
    try:
        resp = await client.get(url, timeout=_WB_CDN_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        brand = (data.get("selling", {}).get("brand_name") or "").strip()
        name = (data.get("imt_name") or "").strip()
        title = f"{brand} {name}".strip() if brand and name else (brand or name or None)
        raw_desc = (data.get("description") or "").strip()
        description = truncate_to_sentences(raw_desc, 3) if raw_desc else None

        return {"title": title, "description": description}
    except Exception as exc:
        logger.debug("WB CDN card.json failed for %s: %s", article_id, exc)
        return None


async def _fetch_wb_cdn_price(article_id: int, client: httpx.AsyncClient) -> str | None:
    """fetch current price from WB CDN price-history — works from any IP, price in kopecks"""
    vol = article_id // 100000
    part = article_id // 1000
    basket = _wb_basket(article_id)
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/info/price-history.json"
    try:
        resp = await client.get(url, timeout=_WB_CDN_TIMEOUT)
        resp.raise_for_status()
        entries = resp.json()
        if not entries:
            return None
        latest = entries[-1].get("price") or {}
        price_kopecks = latest.get("RUB") or latest.get("KZT")
        if price_kopecks:
            return str(Decimal(price_kopecks) / 100)
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
        if not match:
            return LinkPreviewResponse(title=None, description=None, image_url=None, price=None, source="wildberries")

        article_id = int(match.group(1))
        image_url = _wb_image_url(article_id)

        cdn_data, api_data, cdn_price = await asyncio.gather(
            _fetch_wb_cdn_card(article_id, client),
            _fetch_wb_card_api(article_id, client),
            _fetch_wb_cdn_price(article_id, client),
        )

        title = (cdn_data or {}).get("title")
        description = (cdn_data or {}).get("description")
        # prefer card API sale price; fall back to CDN list price
        price = (api_data or {}).get("price") or cdn_price

        if title:
            return LinkPreviewResponse(
                title=title,
                description=description,
                image_url=image_url,
                price=price,
                source="wildberries",
            )

        # fallback: fetch page HTML
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = WildberriesParser().parse(resp.text, url, hostname)
            return LinkPreviewResponse(
                title=data.title,
                description=data.description,
                image_url=data.image_url or image_url,
                price=str(data.price) if data.price is not None else price,
                source="wildberries",
            )
        except Exception as exc:
            logger.debug("WB page fetch failed for %s: %s", url, exc)

        return LinkPreviewResponse(title=None, description=description, image_url=image_url, price=price, source="wildberries")
