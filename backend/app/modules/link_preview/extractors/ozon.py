"""Ozon product metadata extractor

Ozon short URLs (ozon.kz/t/...) serve a lightweight teaser page with OG tags.
Direct product URLs (ozon.kz/product/slug-ID/) hit Ozon's antibot and return 403.
For those we fall back to extracting the product name from the URL slug.
"""

import logging
import re

import httpx

from app.modules.link_preview.schemas import LinkPreviewResponse
from app.modules.marketplace.parsers import OzonParser

logger = logging.getLogger(__name__)

_PRODUCT_SLUG_RE = re.compile(r"/product/([a-z0-9][a-z0-9-]*?)-(\d{5,})/?", re.IGNORECASE)

# hosts an og:url is permitted to point at before we follow it (defense-in-depth)
_OZON_HOSTS = frozenset({"ozon.ru", "www.ozon.ru", "ozon.kz", "www.ozon.kz"})


def _title_from_slug(url: str) -> str | None:
    """derive a human-readable title from an Ozon product URL slug"""
    m = _PRODUCT_SLUG_RE.search(url)
    if not m:
        return None
    slug = m.group(1)  # e.g. "sabo-sabrosso-bear"
    return " ".join(word.capitalize() for word in slug.split("-"))


class OzonExtractor:
    async def extract(self, url: str, hostname: str, client: httpx.AsyncClient) -> LinkPreviewResponse:
        html: str | None = None
        final_url = url
        try:
            resp = await client.get(url)
            final_url = str(resp.url)
            # check antibot before raising — antibot pages return 403
            if "Antibot Challenge" in resp.text:
                logger.debug("Ozon antibot for %s (final: %s)", url, final_url)
            else:
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            logger.debug("Ozon page fetch failed for %s: %s", url, exc)

        if html:
            parser = OzonParser()
            data = parser.parse(html, final_url, hostname)

            # teaser pages (short URL landing) have title/image but no price;
            # try the canonical og:url to get the full product page with JSON-LD
            if data.price is None:
                from urllib.parse import urlparse
                from app.modules.marketplace.parsers import _meta_content
                og_url = _meta_content(html, "og:url")
                # only follow an og:url that is itself a valid Ozon product URL —
                # never trust HTML to hand us an arbitrary outbound target
                og_parsed = urlparse(og_url) if og_url else None
                og_host = (og_parsed.hostname or "").lower() if og_parsed else ""
                if (
                    og_parsed
                    and og_parsed.scheme == "https"
                    and og_host in _OZON_HOSTS
                    and og_url != final_url
                    and "/product/" in og_parsed.path
                ):
                    try:
                        resp2 = await client.get(og_url)
                        if resp2.status_code == 200 and "Antibot Challenge" not in resp2.text:
                            data2 = parser.parse(resp2.text, og_url, hostname)
                            if data2.price is not None:
                                data = data2
                    except Exception as exc:
                        logger.debug("Ozon og:url fetch failed for %s: %s", og_url, exc)

            price = str(data.price) if data.price is not None else None
            return LinkPreviewResponse(
                title=data.title,
                description=data.description,
                image_url=data.image_url,
                price=price,
                currency=data.currency if price else None,
                source="ozon",
            )

        # antibot or fetch failure — use redirect URL slug for at least the title
        return LinkPreviewResponse(
            title=_title_from_slug(final_url) or _title_from_slug(url),
            description=None,
            image_url=None,
            price=None,
            currency=None,
            source="ozon",
        )
