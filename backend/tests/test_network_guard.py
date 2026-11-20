"""The suite cannot reach the network: the autouse `_no_network` fixture fails every connection."""

import asyncio
import socket

import httpx
import pytest

from tests.conftest import NetworkBlocked


def test_plain_sockets_cannot_connect():
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, pytest.raises(NetworkBlocked):
        sock.connect_ex(("127.0.0.1", 9))


def test_http_clients_cannot_connect():
    with pytest.raises(NetworkBlocked):
        httpx.get("http://127.0.0.1:9/", timeout=1, trust_env=False)

    async def fetch() -> None:
        async with httpx.AsyncClient(trust_env=False) as client:
            await client.get("http://127.0.0.1:9/", timeout=1)

    with pytest.raises(BaseException) as raised:  # anyio wraps the error in an exception group
        asyncio.run(fetch())
    assert raised.group_contains(NetworkBlocked) or isinstance(raised.value, NetworkBlocked)


def test_storage_calls_without_the_fake_cannot_connect():
    from botocore.exceptions import BotoCoreError

    from app.core import s3

    s3.get_s3_client.cache_clear()
    try:
        with pytest.raises((NetworkBlocked, BotoCoreError)):
            s3.download_bytes(s3.get_s3_client(), "test-bucket", "images/a.jpg")
    finally:
        s3.get_s3_client.cache_clear()
