"""Wildberries product metadata extractor

Strategy:
1. Wildberries public card API (works from datacenter IPs, returns title + price)
2. Fetch page HTML and parse with WildberriesParser
"""

import logging
import re
from decimal import Decimal, InvalidOperation

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import WildberriesParser

logger = logging.getLogger(__name__)

_WB_CARD_API_TIMEOUT = 8.0


def _wb_image_url(article_id: int) -> str:
    vol = article_id // 100000
    part = article_id // 1000
    thresholds = [
        143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601,
        1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269,
    ]
    basket = next((f"{i + 1:02d}" for i, t in enumerate(thresholds) if vol < t), "20")
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article_id}/images/big/1.webp"


async def _fetch_wb_card_api(article_id: int, client: httpx.AsyncClient) -> dict | None:
    try:
        api_url = (
            f"https://card.wb.ru/cards/v2/detail"
            f"?appType=1&curr=rub&dest=-1257786&nm={article_id}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
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
        brand = (product.get("brand") or "").strip()
        name = (product.get("name") or "").strip()
        title = f"{brand} {name}".strip() if brand and name else (brand or name or None)

        price: str | None = None
        sale_price_u = product.get("salePriceU") or product.get("priceU")
        if sale_price_u:
            try:
                price = str(Decimal(sale_price_u) / 100)
            except (InvalidOperation, TypeError):
                pass

        return {
            "title": title,
            "price": price,
            "image_url": _wb_image_url(article_id),
        }
    except Exception as exc:
        logger.debug("WB card API failed for article %s: %s", article_id, exc)
        return None


class WildberriesExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        match = re.search(r"/catalog/(\d+)/", url)
        if match:
            article_id = int(match.group(1))
            api_data = await _fetch_wb_card_api(article_id, client)
            if api_data and api_data.get("title"):
                return LinkPreviewResponse(
                    title=api_data["title"],
                    description=None,
                    image_url=api_data.get("image_url"),
                    price=api_data.get("price"),
                    source="wildberries",
                )
            # api returned image url even if title missing
            if api_data and api_data.get("image_url"):
                image_url = api_data["image_url"]
            elif match:
                image_url = _wb_image_url(article_id)
            else:
                image_url = None
        else:
            image_url = None

        # fallback: fetch page and parse HTML
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            parser = WildberriesParser()
            data = parser.parse(html, url, hostname)
            return LinkPreviewResponse(
                title=data.title,
                description=data.description,
                image_url=data.image_url or image_url,
                price=str(data.price) if data.price is not None else None,
                source="wildberries",
            )
        except Exception as exc:
            logger.debug("WB page fetch failed for %s: %s", url, exc)

        return LinkPreviewResponse(
            title=None,
            description=None,
            image_url=image_url,
            price=None,
            source="wildberries",
        )
