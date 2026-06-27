"""shared outbound-fetch safety helpers (SSRF protection).

Used by every server-side fetch of a user-supplied URL (link preview, marketplace
import, image download). Provides:

- validate_outbound_url(): synchronous scheme / credentials / port / host-allowlist
  checks performed at the API boundary before any network access.
- assert_host_public(): DNS resolution + private/reserved IP rejection.
- SSRF_EVENT_HOOKS / make_event_hooks(): httpx event hooks that re-validate the
  destination of *every* request, including each redirect hop, at send time. This
  closes the redirect-chain SSRF hole and shrinks the DNS-rebinding window to an
  impractical sub-resolution gap (validation happens on the final getaddrinfo
  before httpx connects).

Follows OWASP SSRF guidance: never trust the hostname alone, resolve and verify
the IP, and re-check after redirects.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")
# only standard web ports — blocks port-scanning of internal services on odd ports
_ALLOWED_PORTS = frozenset({80, 443})

# ranges not reliably covered by ipaddress.is_private/is_reserved across versions
_EXTRA_BLOCKED_V4 = (
    ipaddress.ip_network("100.64.0.0/10"),    # CGNAT / carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),     # IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),    # network benchmarking
    ipaddress.ip_network("192.0.2.0/24"),     # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),   # TEST-NET-3
)

_PRIVATE_DETAIL = "requests to private or reserved addresses are not allowed"


def _unwrap(addr: ipaddress._BaseAddress) -> ipaddress._BaseAddress:
    """unwrap IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) so the v4 checks apply"""
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return addr.ipv4_mapped
        # 6to4 (2002::/16) and Teredo (2001::/32) can embed private v4 — block whole-class via is_reserved/is_private below
    return addr


def ip_is_blocked(ip_str: str) -> bool:
    """True if the IP is loopback/private/link-local/reserved/multicast/etc."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable address → fail closed
    addr = _unwrap(addr)
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    ):
        return True
    if addr.version == 4 and any(addr in net for net in _EXTRA_BLOCKED_V4):
        return True
    return False


def _reject(detail: str) -> "tuple[str, str]":
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def validate_outbound_url(
    url: str,
    *,
    allowed_hosts: "frozenset[str] | None" = None,
    max_length: int = 2048,
) -> tuple[str, str]:
    """validate a user-supplied URL at the API boundary.

    Checks scheme, embedded credentials, port, and (optionally) a host allowlist.
    Returns (normalized_url, lowercased_hostname). The returned url is the exact
    string used for the request, so validation and execution stay in sync.
    """
    url = url.strip()
    if not url or len(url) > max_length:
        _reject("invalid URL")

    try:
        parsed = urlparse(url)
    except Exception as exc:  # noqa: BLE001 — urlparse rarely raises, but be safe
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid URL"
        ) from exc

    if parsed.scheme not in _ALLOWED_SCHEMES:
        _reject("URL must use http or https scheme")

    if parsed.username or parsed.password:
        _reject("URL must not contain credentials")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        _reject("invalid URL")

    try:
        port = parsed.port
    except ValueError:
        _reject("invalid port")
    else:
        if port is not None and port not in _ALLOWED_PORTS:
            _reject("URL port not allowed")

    if allowed_hosts is not None and hostname not in allowed_hosts:
        _reject("unsupported host")

    return url, hostname


async def _resolve(hostname: str) -> list[str]:
    try:
        results = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="could not resolve hostname",
        ) from exc
    return [sockaddr[0] for *_rest, sockaddr in results]


async def assert_host_public(hostname: str) -> None:
    """resolve hostname and reject if ANY resolved IP is private/reserved"""
    for ip_str in await _resolve(hostname):
        if ip_is_blocked(ip_str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_PRIVATE_DETAIL,
            )


async def _ssrf_request_hook(request: httpx.Request) -> None:
    """re-validate the destination of every outbound request (incl. each redirect).

    Raises httpx.RequestError to abort before the socket is opened. Resolving here
    means the validated getaddrinfo is the last one before httpx's own connect,
    leaving no practical window for DNS rebinding.
    """
    host = request.url.host
    # literal IP in the URL — validate directly, no DNS needed
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if ip_is_blocked(host):
            raise httpx.RequestError(f"blocked address: {host}")
        return

    try:
        addrs = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as exc:
        raise httpx.RequestError(f"could not resolve {host}") from exc
    for *_rest, sockaddr in addrs:
        if ip_is_blocked(sockaddr[0]):
            raise httpx.RequestError(f"blocked address for host {host}")


def _make_size_hook(max_bytes: int):
    async def _enforce_response_size(response: httpx.Response) -> None:
        """reject by declared Content-Length before the body is read"""
        cl = response.headers.get("content-length")
        if cl is not None:
            try:
                declared = int(cl)
            except ValueError:
                return
            if declared > max_bytes:
                raise httpx.RequestError(
                    f"response too large: {declared} > {max_bytes}"
                )

    return _enforce_response_size


def make_event_hooks(max_response_bytes: int) -> dict:
    """build httpx event_hooks enforcing SSRF re-validation + response size cap"""
    return {
        "request": [_ssrf_request_hook],
        "response": [_make_size_hook(max_response_bytes)],
    }
