"""marketplace module tests — parsers, URL validation, SSRF protection, rate limiting"""

import json
import socket
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# validate_import_url
# ---------------------------------------------------------------------------

def test_validate_import_url_accepts_kaspi() -> None:
    from app.modules.marketplace.service import validate_import_url
    url, hostname = validate_import_url("https://kaspi.kz/shop/p/product-123")
    assert hostname == "kaspi.kz"


def test_validate_import_url_accepts_www_kaspi() -> None:
    from app.modules.marketplace.service import validate_import_url
    _, hostname = validate_import_url("https://www.kaspi.kz/shop/p/product-123")
    assert hostname == "www.kaspi.kz"


def test_validate_import_url_accepts_wildberries_ru() -> None:
    from app.modules.marketplace.service import validate_import_url
    _, hostname = validate_import_url("https://wildberries.ru/catalog/12345/detail.aspx")
    assert hostname == "wildberries.ru"


def test_validate_import_url_accepts_wildberries_kz() -> None:
    from app.modules.marketplace.service import validate_import_url
    _, hostname = validate_import_url("https://wildberries.kz/catalog/12345/detail.aspx")
    assert hostname == "wildberries.kz"


def test_validate_import_url_accepts_ozon_ru() -> None:
    from app.modules.marketplace.service import validate_import_url
    _, hostname = validate_import_url("https://ozon.ru/product/something-123/")
    assert hostname == "ozon.ru"


def test_validate_import_url_accepts_ozon_kz() -> None:
    from app.modules.marketplace.service import validate_import_url
    _, hostname = validate_import_url("https://ozon.kz/product/something-123/")
    assert hostname == "ozon.kz"


def test_validate_import_url_strips_surrounding_whitespace() -> None:
    from app.modules.marketplace.service import validate_import_url
    url, _ = validate_import_url("  https://kaspi.kz/shop/product  ")
    assert not url.startswith(" ")
    assert not url.endswith(" ")


def test_validate_import_url_rejects_javascript_scheme() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("javascript:alert(1)")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_data_uri() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("data:text/html,<h1>test</h1>")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_file_scheme() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("file:///etc/passwd")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_ftp_scheme() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("ftp://kaspi.kz/something")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_localhost() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("http://localhost/path")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_127_0_0_1() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("http://127.0.0.1/path")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_unsupported_marketplace() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("https://amazon.com/dp/B001")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_internal_ip() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException) as exc_info:
        validate_import_url("http://10.0.0.1/path")
    assert exc_info.value.status_code == 422


def test_validate_import_url_rejects_plain_text() -> None:
    from app.modules.marketplace.service import validate_import_url
    with pytest.raises(HTTPException):
        validate_import_url("not a url at all")


# ---------------------------------------------------------------------------
# _check_host_not_private (SSRF protection)
# ---------------------------------------------------------------------------

def _addr(ip: str) -> list:
    return [(None, None, None, None, (ip, 0))]


@pytest.mark.asyncio
async def test_check_host_not_private_allows_public_ip() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("1.1.1.1")):
        await _check_host_not_private("kaspi.kz")  # must not raise


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_loopback_127() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("127.0.0.1")):
        with pytest.raises(HTTPException) as exc_info:
            await _check_host_not_private("kaspi.kz")
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_10_range() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("10.0.0.1")):
        with pytest.raises(HTTPException) as exc_info:
            await _check_host_not_private("kaspi.kz")
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_172_16_range() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("172.20.0.1")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("kaspi.kz")


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_192_168_range() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("192.168.1.100")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("kaspi.kz")


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_link_local() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=_addr("169.254.0.1")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("kaspi.kz")


@pytest.mark.asyncio
async def test_check_host_not_private_blocks_ipv6_loopback() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", return_value=[(None, None, None, None, ("::1", 0, 0, 0))]):
        with pytest.raises(HTTPException):
            await _check_host_not_private("kaspi.kz")


@pytest.mark.asyncio
async def test_check_host_not_private_raises_on_dns_failure() -> None:
    from app.modules.marketplace.service import _check_host_not_private
    with patch("app.modules.marketplace.service.socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
        with pytest.raises(HTTPException) as exc_info:
            await _check_host_not_private("doesnotexist.kaspi.kz")
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

def _fake_redis_pipeline(minute_count: int, hour_count: int) -> MagicMock:
    """build a minimal async-context-manager mock for redis.pipeline"""
    pipe = MagicMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[minute_count, True, hour_count, True])

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=pipe)
    ctx.__aexit__ = AsyncMock(return_value=False)

    redis = MagicMock()
    redis.pipeline.return_value = ctx
    return redis


def _settings(per_minute: int = 5, per_hour: int = 30) -> SimpleNamespace:
    return SimpleNamespace(
        marketplace_import_rate_per_minute=per_minute,
        marketplace_import_rate_per_hour=per_hour,
    )


@pytest.mark.asyncio
async def test_rate_limit_passes_under_both_limits() -> None:
    from app.modules.marketplace.service import _check_import_rate_limit
    redis = _fake_redis_pipeline(minute_count=1, hour_count=1)
    await _check_import_rate_limit(redis, uuid4(), _settings())  # must not raise


@pytest.mark.asyncio
async def test_rate_limit_rejects_over_per_minute() -> None:
    from app.modules.marketplace.service import _check_import_rate_limit
    redis = _fake_redis_pipeline(minute_count=6, hour_count=6)
    with pytest.raises(HTTPException) as exc_info:
        await _check_import_rate_limit(redis, uuid4(), _settings(per_minute=5))
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_rejects_over_per_hour() -> None:
    from app.modules.marketplace.service import _check_import_rate_limit
    redis = _fake_redis_pipeline(minute_count=1, hour_count=31)
    with pytest.raises(HTTPException) as exc_info:
        await _check_import_rate_limit(redis, uuid4(), _settings(per_hour=30))
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_passes_exactly_at_limit() -> None:
    from app.modules.marketplace.service import _check_import_rate_limit
    redis = _fake_redis_pipeline(minute_count=5, hour_count=30)
    await _check_import_rate_limit(redis, uuid4(), _settings(per_minute=5, per_hour=30))


# ---------------------------------------------------------------------------
# parsers — JSON-LD extraction
# ---------------------------------------------------------------------------

def _ld_html(data: dict) -> str:
    return f'<html><head><script type="application/ld+json">{json.dumps(data)}</script></head><body></body></html>'


def test_kaspi_parser_extracts_json_ld() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = _ld_html({
        "@type": "Product",
        "name": "Наушники Sony WH-1000XM5",
        "description": "Отличные наушники",
        "image": "https://kaspi.kz/images/product.jpg",
        "offers": {"@type": "Offer", "price": "89999", "priceCurrency": "KZT"},
    })
    product = parser.parse(html, "https://kaspi.kz/shop/p/product-123", "kaspi.kz")

    assert product.title == "Наушники Sony WH-1000XM5"
    assert product.description == "Отличные наушники"
    assert product.price == Decimal("89999")
    assert product.currency == "KZT"
    assert product.image_url == "https://kaspi.kz/images/product.jpg"
    assert product.marketplace == "kaspi"


def test_wildberries_parser_extracts_json_ld() -> None:
    from app.modules.marketplace.parsers import WildberriesParser
    parser = WildberriesParser()
    html = _ld_html({
        "@type": "Product",
        "name": "Кроссовки Nike Air Max",
        "offers": {"@type": "Offer", "price": "5990", "priceCurrency": "RUB"},
    })
    product = parser.parse(html, "https://wildberries.ru/catalog/12345/detail.aspx", "wildberries.ru")

    assert product.title == "Кроссовки Nike Air Max"
    assert product.price == Decimal("5990")
    assert product.currency == "RUB"
    assert product.marketplace == "wildberries"


def test_ozon_parser_extracts_json_ld() -> None:
    from app.modules.marketplace.parsers import OzonParser
    parser = OzonParser()
    html = _ld_html({
        "@type": "Product",
        "name": "Смартфон iPhone 15",
        "offers": {"@type": "Offer", "price": "79900", "priceCurrency": "RUB"},
    })
    product = parser.parse(html, "https://ozon.ru/product/something-123/", "ozon.ru")

    assert product.title == "Смартфон iPhone 15"
    assert product.price == Decimal("79900")
    assert product.marketplace == "ozon"


def test_parser_handles_json_ld_as_array() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = _ld_html([
        {"@type": "WebPage", "name": "Page"},
        {"@type": "Product", "name": "Чайник Tefal", "offers": {"price": "12500", "priceCurrency": "KZT"}},
    ])
    product = parser.parse(html, "https://kaspi.kz/p/1", "kaspi.kz")

    assert product.title == "Чайник Tefal"
    assert product.price == Decimal("12500")


def test_parser_handles_image_as_list_in_json_ld() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = _ld_html({
        "@type": "Product",
        "name": "Test",
        "image": ["https://kaspi.kz/img1.jpg", "https://kaspi.kz/img2.jpg"],
        "offers": {"price": "100", "priceCurrency": "KZT"},
    })
    product = parser.parse(html, "https://kaspi.kz/p/1", "kaspi.kz")
    assert product.image_url == "https://kaspi.kz/img1.jpg"


# ---------------------------------------------------------------------------
# parsers — OpenGraph fallback
# ---------------------------------------------------------------------------

def test_kaspi_parser_falls_back_to_opengraph_when_no_json_ld() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = """
    <html><head>
      <meta property="og:title" content="Sony WH-1000XM5">
      <meta property="og:image" content="https://kaspi.kz/img.jpg">
      <meta property="product:price:amount" content="89999">
      <meta property="product:price:currency" content="KZT">
    </head><body></body></html>
    """
    product = parser.parse(html, "https://kaspi.kz/p/1", "kaspi.kz")

    assert product.title == "Sony WH-1000XM5"
    assert product.price == Decimal("89999")
    assert product.currency == "KZT"
    assert product.image_url == "https://kaspi.kz/img.jpg"


def test_parser_falls_back_to_opengraph_after_broken_json_ld() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = """
    <html><head>
      <script type="application/ld+json">this is not json at all</script>
      <meta property="og:title" content="Fallback Title">
    </head></html>
    """
    product = parser.parse(html, "https://kaspi.kz/p/1", "kaspi.kz")

    assert product.title == "Fallback Title"


# ---------------------------------------------------------------------------
# parsers — HTML fallback
# ---------------------------------------------------------------------------

def test_kaspi_parser_falls_back_to_html_selectors() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = """
    <html><body>
      <h1 class="item-card__meta-title">Телевизор Samsung 55"</h1>
      <div class="item-card__prices-main">149 999 ₸</div>
    </body></html>
    """
    product = parser.parse(html, "https://kaspi.kz/shop/p/tv-456", "kaspi.kz")

    assert product.title == 'Телевизор Samsung 55"'
    assert product.price == Decimal("149999")
    assert product.currency == "KZT"


def test_wildberries_parser_falls_back_to_html_selectors() -> None:
    from app.modules.marketplace.parsers import WildberriesParser
    parser = WildberriesParser()
    html = """
    <html><body>
      <h1 class="product-page__title">Платье летнее</h1>
      <span class="price-block__wallet-price">2 490 ₽</span>
    </body></html>
    """
    product = parser.parse(html, "https://wildberries.ru/catalog/999/detail.aspx", "wildberries.ru")

    assert product.title == "Платье летнее"
    assert product.price == Decimal("2490")
    assert product.currency == "RUB"


def test_ozon_parser_falls_back_to_h1() -> None:
    from app.modules.marketplace.parsers import OzonParser
    parser = OzonParser()
    html = "<html><body><h1>Умные часы Xiaomi Band 8</h1></body></html>"
    product = parser.parse(html, "https://ozon.ru/product/123/", "ozon.ru")

    assert product.title == "Умные часы Xiaomi Band 8"
    assert product.price is None
    assert product.currency is None


# ---------------------------------------------------------------------------
# parsers — missing / empty data
# ---------------------------------------------------------------------------

def test_parser_returns_all_none_when_page_has_no_product_data() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = "<html><body><p>Nothing to extract here</p></body></html>"
    product = parser.parse(html, "https://kaspi.kz/shop/p/product-999", "kaspi.kz")

    assert product.title is None
    assert product.price is None
    assert product.currency is None
    assert product.image_url is None
    assert product.description is None


def test_parser_missing_price_does_not_set_default_currency() -> None:
    from app.modules.marketplace.parsers import KaspiParser
    parser = KaspiParser()
    html = _ld_html({"@type": "Product", "name": "Товар без цены"})
    product = parser.parse(html, "https://kaspi.kz/p/1", "kaspi.kz")

    assert product.title == "Товар без цены"
    assert product.price is None
    assert product.currency is None  # KZT default only set when price is present


# ---------------------------------------------------------------------------
# get_parser
# ---------------------------------------------------------------------------

def test_get_parser_returns_kaspi_for_kaspi_kz() -> None:
    from app.modules.marketplace.parsers import KaspiParser, get_parser
    assert isinstance(get_parser("kaspi.kz"), KaspiParser)


def test_get_parser_returns_kaspi_for_www_kaspi_kz() -> None:
    from app.modules.marketplace.parsers import KaspiParser, get_parser
    assert isinstance(get_parser("www.kaspi.kz"), KaspiParser)


def test_get_parser_returns_wildberries_for_wildberries_kz() -> None:
    from app.modules.marketplace.parsers import WildberriesParser, get_parser
    assert isinstance(get_parser("wildberries.kz"), WildberriesParser)


def test_get_parser_returns_ozon_for_ozon_kz() -> None:
    from app.modules.marketplace.parsers import OzonParser, get_parser
    assert isinstance(get_parser("ozon.kz"), OzonParser)


def test_get_parser_returns_none_for_unsupported_host() -> None:
    from app.modules.marketplace.parsers import get_parser
    assert get_parser("amazon.com") is None


def test_get_parser_returns_none_for_empty_string() -> None:
    from app.modules.marketplace.parsers import get_parser
    assert get_parser("") is None


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------

def test_parse_price_plain_integer() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("89999") == Decimal("89999")


def test_parse_price_with_space_thousands_separator() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("149 999") == Decimal("149999")


def test_parse_price_with_currency_symbol() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("5 990 ₽") == Decimal("5990")


def test_parse_price_european_format_dot_thousands_comma_decimal() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("1.234,56") == Decimal("1234.56")


def test_parse_price_with_decimal_comma() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("29,99") == Decimal("29.99")


def test_parse_price_with_decimal_dot() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("29.99") == Decimal("29.99")


def test_parse_price_returns_none_for_empty_string() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("") is None


def test_parse_price_returns_none_for_non_numeric_text() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("цена по запросу") is None


def test_parse_price_strips_tenge_sign() -> None:
    from app.modules.marketplace.parsers import _parse_price
    assert _parse_price("149 999 ₸") == Decimal("149999")
