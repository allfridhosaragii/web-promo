"""Test pemicu revalidate via HTTP — mock transport, tanpa request live (F)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.revalidate import trigger_revalidate


def _client(status: int, seen: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("x-revalidate-secret")
        seen["body"] = request.read().decode()
        return httpx.Response(status, json={"ok": status == 200})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_trigger_posts_secret_header_and_paths() -> None:
    seen: dict = {}
    ok = trigger_revalidate(
        "http://web:3000",
        "rahasia",
        paths=["/", "/promo/abc"],
        client=_client(200, seen),
    )
    assert ok is True
    assert seen["url"] == "http://web:3000/api/revalidate"
    assert seen["secret"] == "rahasia"
    assert "/promo/abc" in seen["body"]


def test_trigger_returns_false_on_401_and_without_config() -> None:
    seen: dict = {}
    assert (
        trigger_revalidate("http://web:3000", "salah", client=_client(401, seen)) is False
    )
    assert trigger_revalidate("http://web:3000", "", client=_client(200, seen)) is False
    assert trigger_revalidate("", "rahasia", client=_client(200, seen)) is False


def test_trigger_returns_false_on_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("web mati", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert trigger_revalidate("http://web:3000", "rahasia", client=client) is False
