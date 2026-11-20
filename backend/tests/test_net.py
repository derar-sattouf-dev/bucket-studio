"""SSRF guard (app.core.net)."""

import httpx
import pytest

from app.core import net
from app.core.net import FetchError, UnsafeURLError

PUBLIC_IP = "93.184.216.34"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("2002:7f00:1::", False),  # 6to4 wrapping 127.0.0.1
        ("2002:0808:0808::", True),  # 6to4 wrapping 8.8.8.8
        ("64:ff9b::7f00:1", False),  # NAT64 wrapping 127.0.0.1
        ("64:ff9b::a00:1", False),  # NAT64 wrapping 10.0.0.1
        ("8.8.8.8", True),
        (PUBLIC_IP, True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),  # cloud metadata
        ("100.64.0.1", False),  # CGNAT
        ("0.0.0.0", False),
        ("::1", False),
        ("fc00::1", False),
        ("fe80::1", False),
        ("::ffff:127.0.0.1", False),  # IPv4-mapped loopback
        ("224.0.0.1", False),
        ("not-an-ip", False),
    ],
)
def test_is_public_ip(address, expected):
    assert net.is_public_ip(address) is expected


@pytest.fixture
def fake_dns(monkeypatch):
    table: dict[str, list[str]] = {}

    async def _resolve(host, port):
        if host not in table:
            raise UnsafeURLError("Host could not be resolved")
        return table[host]

    monkeypatch.setattr(net, "_resolve", _resolve)
    return table


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/a.png",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "http://example.com:22/",
        "http:///nohost",
        "",
        "http://example.com/" + "a" * 3000,
    ],
)
async def test_rejects_malformed_or_disallowed(url, fake_dns):
    fake_dns["example.com"] = [PUBLIC_IP]
    with pytest.raises(UnsafeURLError):
        await net.validate_public_url(url)


async def test_rejects_hostname_resolving_to_private_ip(fake_dns):
    fake_dns["internal.example.com"] = ["10.0.0.5"]
    with pytest.raises(UnsafeURLError):
        await net.validate_public_url("https://internal.example.com/image.png")


async def test_rejects_when_any_resolved_address_is_private(fake_dns):
    fake_dns["mixed.example.com"] = [PUBLIC_IP, "127.0.0.1"]
    with pytest.raises(UnsafeURLError):
        await net.validate_public_url("https://mixed.example.com/")


async def test_pins_connection_to_validated_ip(fake_dns):
    fake_dns["cdn.example.com"] = [PUBLIC_IP]
    target = await net.validate_public_url("https://cdn.example.com/img.png?x=1")
    assert net._pinned_url(target) == f"https://{PUBLIC_IP}/img.png?x=1"
    assert net._host_header(target) == "cdn.example.com"


@pytest.fixture
def mock_transport(monkeypatch):
    routes: dict[str, httpx.Response] = {}
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes[request.headers["host"] + request.url.path]

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    monkeypatch.setattr(net, "_client", client)
    return routes, seen


async def test_fetches_image_with_host_header(fake_dns, mock_transport):
    routes, seen = mock_transport
    fake_dns["img.example.com"] = [PUBLIC_IP]
    routes["img.example.com/a.png"] = httpx.Response(200, headers={"content-type": "image/png"}, content=b"PNG")

    result = await net.safe_get("http://img.example.com/a.png", max_bytes=100, require_image=True)

    assert result.content == b"PNG"
    assert seen[0].url.host == PUBLIC_IP
    assert seen[0].headers["host"] == "img.example.com"


async def test_redirect_to_private_address_is_blocked(fake_dns, mock_transport):
    routes, _ = mock_transport
    fake_dns["public.example.com"] = [PUBLIC_IP]
    fake_dns["metadata.example.com"] = ["169.254.169.254"]
    routes["public.example.com/start"] = httpx.Response(302, headers={"location": "http://metadata.example.com/latest"})

    with pytest.raises(UnsafeURLError):
        await net.safe_get("http://public.example.com/start", max_bytes=100)


async def test_body_size_limit(fake_dns, mock_transport):
    routes, _ = mock_transport
    fake_dns["big.example.com"] = [PUBLIC_IP]
    routes["big.example.com/big.jpg"] = httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"x" * 101)

    with pytest.raises(FetchError):
        await net.safe_get("http://big.example.com/big.jpg", max_bytes=100)


async def test_svg_is_not_accepted_as_image(fake_dns, mock_transport):
    routes, _ = mock_transport
    fake_dns["svg.example.com"] = [PUBLIC_IP]
    routes["svg.example.com/x.svg"] = httpx.Response(200, headers={"content-type": "image/svg+xml"}, content=b"<svg/>")

    with pytest.raises(FetchError):
        await net.safe_get("http://svg.example.com/x.svg", max_bytes=100, require_image=True)
