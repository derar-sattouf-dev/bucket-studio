"""Outbound HTTP fetching of user- or LLM-supplied URLs, hardened against SSRF.

Every URL that did not come from our own configuration MUST be fetched through `safe_get`.

Protections:
* only http/https, no embedded credentials, only standard web ports;
* the hostname is resolved once and **every** resolved address must be globally routable
  (blocks loopback, RFC 1918, link-local / cloud metadata, CGNAT, ULA, IPv4-mapped IPv6, …);
* the connection is pinned to the validated IP (Host header + TLS SNI keep the original name),
  so a second DNS lookup cannot be used for DNS rebinding;
* redirects are followed manually and every hop is re-validated;
* the response body is streamed with a hard byte limit and a total timeout.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})
MAX_REDIRECTS = 5
MAX_URL_LENGTH = 2048

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# The formats the app can decode. SVG in particular is excluded: it can carry script.
SAFE_IMAGE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


class UnsafeURLError(ValueError):
    """The URL is malformed or points at a non-public destination."""


class FetchError(Exception):
    """The remote request failed (network error, bad status, too large, wrong type)."""


@dataclass(frozen=True)
class FetchResult:
    content: bytes
    content_type: str


@dataclass(frozen=True)
class _Target:
    url: str  # original URL (validated)
    host: str  # original hostname
    ip: str  # pinned, validated address
    port: int
    scheme: str


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Addresses that embed an IPv4 address are judged by that address: `2002:7f00:1::` (6to4)
        # or `64:ff9b::7f00:1` (NAT64) would otherwise look public while routing to 127.0.0.1.
        embedded = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)
        if embedded is None and ip in _NAT64:
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None:
            ip = embedded
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


async def _resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError("Host could not be resolved") from exc
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise UnsafeURLError("Host could not be resolved")
    return addresses


async def validate_public_url(url: str) -> _Target:
    """Validate scheme/host/port and resolve to a public IP. Raises UnsafeURLError."""
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("Invalid URL")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("Invalid URL") from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with credentials are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURLError("URL has no host")
    port = port or (443 if scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError("Port not allowed")

    addresses = await _resolve(host, port)
    if not all(is_public_ip(a) for a in addresses):
        raise UnsafeURLError("URL resolves to a non-public address")

    return _Target(url=url, host=host, ip=addresses[0], port=port, scheme=scheme)


def _pinned_url(target: _Target) -> str:
    parts = urlsplit(target.url)
    ip_host = f"[{target.ip}]" if ":" in target.ip else target.ip
    default_port = 443 if target.scheme == "https" else 80
    netloc = ip_host if target.port == default_port else f"{ip_host}:{target.port}"
    return urlunsplit((target.scheme, netloc, parts.path or "/", parts.query, ""))


def _host_header(target: _Target) -> str:
    default_port = 443 if target.scheme == "https" else 80
    return target.host if target.port == default_port else f"{target.host}:{target.port}"


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,  # never route through env-configured proxies (would bypass pinning)
            # No keep-alive: connections are keyed by the pinned IP, and reusing a TLS
            # connection verified for one hostname for another host on the same IP is wrong.
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=0),
        )
    return _client


async def aclose() -> None:
    """Close the shared client (call on application shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def safe_get(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 15.0,  # noqa: ASYNC109 — total deadline incl. redirects, enforced via asyncio.wait_for
    require_image: bool = False,
) -> FetchResult:
    """GET a public URL with SSRF protection, a size cap and a total timeout.

    Raises UnsafeURLError for disallowed destinations and FetchError for transport/HTTP errors.
    """
    try:
        return await asyncio.wait_for(
            _safe_get(url, max_bytes=max_bytes, require_image=require_image),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise FetchError("Request timed out") from exc


async def _safe_get(url: str, *, max_bytes: int, require_image: bool) -> FetchResult:
    client = _get_client()
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        target = await validate_public_url(current)
        request_headers = {"User-Agent": BROWSER_USER_AGENT, "Host": _host_header(target)}
        extensions = {"sni_hostname": target.host} if target.scheme == "https" else {}
        request = client.build_request("GET", _pinned_url(target), headers=request_headers, extensions=extensions)
        try:
            response = await client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise FetchError("Could not reach the remote server") from exc

        try:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("Redirect without location")
                current = urljoin(current, location)
                continue

            if response.status_code >= 400:
                raise FetchError(f"Remote server returned HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if require_image and content_type not in SAFE_IMAGE_TYPES:
                raise FetchError("URL does not point to a supported image")

            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise FetchError("Remote file is too large")

            chunks: list[bytes] = []
            received = 0
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise FetchError("Remote file is too large")
                chunks.append(chunk)
            return FetchResult(content=b"".join(chunks), content_type=content_type)
        except httpx.HTTPError as exc:
            raise FetchError("Error while downloading the remote file") from exc
        finally:
            await response.aclose()

    raise FetchError("Too many redirects")
