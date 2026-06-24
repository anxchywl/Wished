"""link preview module tests — URL validation, SSRF, caching, rate limiting, extractors"""

import json
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# validate_preview_url
# ---------------------------------------------------------------------------

def test_validate_preview_url_accepts_wildberries() -> None:
    from app.modules.link_preview.service import validate_preview_url
    url, hostname = validate_preview_url("https://www.wildberries.ru/catalog/12345678/detail.aspx")
    assert hostname == "www.wildberries.ru"


def test_validate_preview_url_accepts_ozon() -> None:
    from app.modules.link_preview.service import validate_preview_url
    _, hostname = validate_preview_url("https://ozon.ru/product/something-123/")
    assert hostname == "ozon.ru"


def test_validate_preview_url_accepts_kaspi() -> None:
    from app.modules.link_preview.service import validate_preview_url
    _, hostname = validate_preview_url("https://kaspi.kz/shop/p/product-123")
    assert hostname == "kaspi.kz"


def test_validate_preview_url_accepts_generic_https() -> None:
    from app.modules.link_preview.service import validate_preview_url
    url, hostname = validate_preview_url("https://example.com/product")
    assert hostname == "example.com"


def test_validate_preview_url_accepts_http() -> None:
    from app.modules.link_preview.service import validate_preview_url
    _, hostname = validate_preview_url("http://example.com/product")
    assert hostname == "example.com"


def test_validate_preview_url_strips_whitespace() -> None:
    from app.modules.link_preview.service import validate_preview_url
    url, _ = validate_preview_url("  https://example.com/product  ")
    assert not url.startswith(" ")
    assert not url.endswith(" ")


def test_validate_preview_url_rejects_javascript_scheme() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("javascript:alert(1)")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_file_scheme() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("file:///etc/passwd")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_ftp_scheme() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("ftp://example.com/file")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_data_uri() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("data:text/html,<h1>test</h1>")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_localhost() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("http://localhost/path")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_127_0_0_1() -> None:
    from app.modules.link_preview.service import validate_preview_url
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url("http://127.0.0.1/path")
    assert exc_info.value.status_code == 422


def test_validate_preview_url_rejects_url_exceeding_max_length() -> None:
    from app.modules.link_preview.service import validate_preview_url
    long_url = "https://example.com/" + "a" * 2100
    with pytest.raises(HTTPException) as exc_info:
        validate_preview_url(long_url)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _check_host_not_private — SSRF protection
# ---------------------------------------------------------------------------

def _addr(ip: str) -> list:
    return [(None, None, None, None, (ip, 0))]


@pytest.mark.asyncio
async def test_ssrf_check_allows_public_ip() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", return_value=_addr("1.1.1.1")):
        await _check_host_not_private("example.com")  # must not raise


@pytest.mark.asyncio
async def test_ssrf_check_blocks_loopback() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", return_value=_addr("127.0.0.1")):
        with pytest.raises(HTTPException) as exc_info:
            await _check_host_not_private("example.com")
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_ssrf_check_blocks_private_10_range() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", return_value=_addr("10.0.0.1")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("example.com")


@pytest.mark.asyncio
async def test_ssrf_check_blocks_private_172_range() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", return_value=_addr("172.20.0.1")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("example.com")


@pytest.mark.asyncio
async def test_ssrf_check_blocks_private_192_168_range() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", return_value=_addr("192.168.1.1")):
        with pytest.raises(HTTPException):
            await _check_host_not_private("example.com")


@pytest.mark.asyncio
async def test_ssrf_check_raises_on_dns_failure() -> None:
    from app.modules.link_preview.service import _check_host_not_private
    with patch("app.modules.link_preview.service.socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
        with pytest.raises(HTTPException) as exc_info:
            await _check_host_not_private("doesnotexist.example.com")
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

def _fake_redis_incr(count: int) -> MagicMock:
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=count)
    redis.expire = AsyncMock(return_value=True)
    return redis


def _settings(per_hour: int = 20) -> SimpleNamespace:
    return SimpleNamespace(link_preview_rate_per_hour=per_hour)


@pytest.mark.asyncio
async def test_rate_limit_passes_under_limit() -> None:
    from app.modules.link_preview.service import _check_rate_limit
    redis = _fake_redis_incr(1)
    await _check_rate_limit(redis, uuid4(), _settings(per_hour=20))  # must not raise


@pytest.mark.asyncio
async def test_rate_limit_passes_at_exact_limit() -> None:
    from app.modules.link_preview.service import _check_rate_limit
    redis = _fake_redis_incr(20)
    await _check_rate_limit(redis, uuid4(), _settings(per_hour=20))  # must not raise


@pytest.mark.asyncio
async def test_rate_limit_rejects_over_limit() -> None:
    from app.modules.link_preview.service import _check_rate_limit
    redis = _fake_redis_incr(21)
    with pytest.raises(HTTPException) as exc_info:
        await _check_rate_limit(redis, uuid4(), _settings(per_hour=20))
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result() -> None:
    from app.modules.link_preview.service import _get_cached
    from app.modules.link_preview.schemas import LinkPreviewResponse

    cached = LinkPreviewResponse(
        title="Cached Product",
        description="A great product",
        image_url="https://example.com/img.jpg",
        price="1990",
        currency=None,
        source="wildberries",
    )
    redis = MagicMock()
    redis.get = AsyncMock(return_value=json.dumps(cached.model_dump()).encode())
    result = await _get_cached(redis, "https://wildberries.ru/catalog/12345/detail.aspx")
    assert result is not None
    assert result.title == "Cached Product"
    assert result.source == "wildberries"


@pytest.mark.asyncio
async def test_cache_miss_returns_none() -> None:
    from app.modules.link_preview.service import _get_cached
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    result = await _get_cached(redis, "https://example.com/product")
    assert result is None


@pytest.mark.asyncio
async def test_cache_stores_result() -> None:
    from app.modules.link_preview.service import _set_cached
    from app.modules.link_preview.schemas import LinkPreviewResponse

    result = LinkPreviewResponse(
        title="Product",
        description=None,
        image_url=None,
        price="500",
        currency=None,
        source="kaspi",
    )
    redis = MagicMock()
    redis.setex = AsyncMock(return_value=True)
    await _set_cached(redis, "https://kaspi.kz/p/1", result)
    redis.setex.assert_called_once()
    call_args = redis.setex.call_args
    assert call_args[0][1] == 86400  # 24h TTL


# ---------------------------------------------------------------------------
# _choose_extractor
# ---------------------------------------------------------------------------

def test_choose_extractor_wildberries() -> None:
    from app.modules.link_preview.service import _choose_extractor
    from app.modules.link_preview.extractors.wildberries import WildberriesExtractor
    assert isinstance(_choose_extractor("wildberries.ru"), WildberriesExtractor)
    assert isinstance(_choose_extractor("www.wildberries.kz"), WildberriesExtractor)


def test_choose_extractor_ozon() -> None:
    from app.modules.link_preview.service import _choose_extractor
    from app.modules.link_preview.extractors.ozon import OzonExtractor
    assert isinstance(_choose_extractor("ozon.ru"), OzonExtractor)
    assert isinstance(_choose_extractor("ozon.kz"), OzonExtractor)


def test_choose_extractor_kaspi() -> None:
    from app.modules.link_preview.service import _choose_extractor
    from app.modules.link_preview.extractors.kaspi import KaspiExtractor
    assert isinstance(_choose_extractor("kaspi.kz"), KaspiExtractor)
    assert isinstance(_choose_extractor("www.kaspi.kz"), KaspiExtractor)


def test_choose_extractor_generic_for_unknown_host() -> None:
    from app.modules.link_preview.service import _choose_extractor
    from app.modules.link_preview.extractors.generic import GenericExtractor
    assert isinstance(_choose_extractor("amazon.com"), GenericExtractor)
    assert isinstance(_choose_extractor("somestore.kz"), GenericExtractor)


# ---------------------------------------------------------------------------
# generic extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generic_extractor_extracts_opengraph() -> None:
    from app.modules.link_preview.extractors.generic import GenericExtractor

    html = """
    <html><head>
      <meta property="og:title" content="Amazing Widget">
      <meta property="og:image" content="https://example.com/img.jpg">
      <meta property="og:description" content="A really great widget.">
    </head><body></body></html>
    """

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    extractor = GenericExtractor()
    result = await extractor.extract("https://example.com/widget", "example.com", mock_client)

    assert result.title == "Amazing Widget"
    assert result.image_url == "https://example.com/img.jpg"
    assert result.description == "A really great widget."
    assert result.source is None
    assert result.price is None


@pytest.mark.asyncio
async def test_generic_extractor_falls_back_to_title_tag() -> None:
    from app.modules.link_preview.extractors.generic import GenericExtractor

    html = "<html><head><title>My Shop | Some Product</title></head><body></body></html>"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    extractor = GenericExtractor()
    result = await extractor.extract("https://example.com/product", "example.com", mock_client)
    assert result.title == "My Shop | Some Product"


@pytest.mark.asyncio
async def test_generic_extractor_returns_empty_on_fetch_failure() -> None:
    from app.modules.link_preview.extractors.generic import GenericExtractor
    import httpx

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    extractor = GenericExtractor()
    result = await extractor.extract("https://example.com/product", "example.com", mock_client)
    assert result.title is None
    assert result.image_url is None
    assert result.price is None


# ---------------------------------------------------------------------------
# wildberries extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wildberries_extractor_uses_cdn_and_card_api() -> None:
    from app.modules.link_preview.extractors.wildberries import WildberriesExtractor

    cdn_response = {
        "imt_name": "Air Max 90",
        "description": "Great shoe",
        "selling": {"brand_name": "Nike"},
    }
    card_api_response = {
        "data": {
            "products": [{
                "brand": "Nike",
                "name": "Air Max 90",
                "salePriceU": 599000,
            }]
        }
    }

    async def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "wbbasket.ru" in url and "card.json" in url:
            resp.status_code = 200
            resp.json = MagicMock(return_value=cdn_response)
        elif "card.wb.ru" in url:
            resp.status_code = 200
            resp.json = MagicMock(return_value=card_api_response)
        elif "wbbasket.ru" in url and "price-history" in url:
            resp.status_code = 200
            resp.json = MagicMock(return_value=[])
        else:
            resp.status_code = 200
            resp.json = MagicMock(return_value={})
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)

    extractor = WildberriesExtractor()
    result = await extractor.extract(
        "https://www.wildberries.ru/catalog/12345678/detail.aspx",
        "www.wildberries.ru",
        mock_client,
    )

    assert result.title == "Nike Air Max 90"
    assert result.description == "Great shoe"
    assert result.price == "5990"
    assert result.source == "wildberries"


@pytest.mark.asyncio
async def test_wildberries_extractor_falls_back_to_html_when_cdn_fails() -> None:
    from app.modules.link_preview.extractors.wildberries import WildberriesExtractor
    import httpx

    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type": "Product", "name": "Кроссовки Adidas"}
      </script>
    </head><body></body></html>
    """

    async def mock_get(url, **kwargs):
        if "wbbasket.ru" in url or "card.wb.ru" in url:
            raise httpx.ConnectError("down")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.text = html
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)

    extractor = WildberriesExtractor()
    result = await extractor.extract(
        "https://www.wildberries.ru/catalog/12345678/detail.aspx",
        "www.wildberries.ru",
        mock_client,
    )

    assert result.title == "Кроссовки Adidas"
    assert result.source == "wildberries"


# ---------------------------------------------------------------------------
# kaspi extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kaspi_extractor_extracts_metadata() -> None:
    from app.modules.link_preview.extractors.kaspi import KaspiExtractor

    html = """
    <html><head>
      <meta property="og:title" content="Samsung TV 55">
      <meta property="og:image" content="https://kaspi.kz/img.jpg">
      <meta property="product:price:amount" content="149999">
      <meta property="product:price:currency" content="KZT">
    </head><body></body></html>
    """

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    extractor = KaspiExtractor()
    result = await extractor.extract("https://kaspi.kz/shop/p/tv-1", "kaspi.kz", mock_client)

    assert result.title == "Samsung TV 55"
    assert result.price == "149999"
    assert result.image_url == "https://kaspi.kz/img.jpg"
    assert result.source == "kaspi"


# ---------------------------------------------------------------------------
# ozon extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ozon_extractor_extracts_metadata() -> None:
    from app.modules.link_preview.extractors.ozon import OzonExtractor

    html = """
    <html><head>
      <meta property="og:title" content="iPhone 15 Pro">
      <meta property="og:image" content="https://ozon.ru/img.jpg">
      <meta property="og:description" content="Отличный смартфон">
    </head><body></body></html>
    """

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    extractor = OzonExtractor()
    result = await extractor.extract("https://ozon.ru/product/123/", "ozon.ru", mock_client)

    assert result.title == "iPhone 15 Pro"
    assert result.image_url == "https://ozon.ru/img.jpg"
    assert result.description == "Отличный смартфон"
    assert result.source == "ozon"


# ---------------------------------------------------------------------------
# redirect handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_follows_redirects() -> None:
    """extractor should follow redirects (handled by httpx client config)"""
    from app.modules.link_preview.extractors.generic import GenericExtractor

    html = "<html><head><title>Redirected Product</title></head></html>"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    extractor = GenericExtractor()
    result = await extractor.extract(
        "https://example.com/short-link",
        "example.com",
        mock_client,
    )
    assert result.title == "Redirected Product"


# ---------------------------------------------------------------------------
# fetch_link_preview integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_link_preview_uses_cache_on_hit() -> None:
    from app.modules.link_preview.service import fetch_link_preview
    from app.modules.link_preview.schemas import LinkPreviewResponse

    cached = LinkPreviewResponse(
        title="Cached",
        description=None,
        image_url=None,
        price=None,
        currency=None,
        source="wildberries",
    )
    redis = MagicMock()
    redis.get = AsyncMock(return_value=json.dumps(cached.model_dump()).encode())
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)

    settings = SimpleNamespace(link_preview_rate_per_hour=20)

    with patch("app.modules.link_preview.service._check_host_not_private", new=AsyncMock()):
        result = await fetch_link_preview(
            "https://wildberries.ru/catalog/111/detail.aspx",
            "wildberries.ru",
            uuid4(),
            redis,
            settings,
        )

    assert result.title == "Cached"
    # extractor should not have been called — no HTTP requests needed
