"""Test konektor BNI — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.bank_bni import BankBNIConnector, extract_detail_fields, extract_promo_links
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "bni"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert links == expected["listing_links"]
    assert not any("/promo/preview" in u or "/sliders" in u for u in links)


def test_detail_1_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_1"]
    html = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("value_amount") == expected["value_amount"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_detail_2_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_2"]
    html = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("value_amount") == expected["value_amount"]
    assert extracted.get("min_purchase") == expected["min_purchase"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_robots_disallow_preview_sliders_and_main_domain() -> None:
    c = BankBNIConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nAllow: /\nDisallow: /sliders\nDisallow: /promo/preview/*\n",
        "https://bniexperience.bni.co.id/",
    )
    assert c._allowed_by_robots("https://bniexperience.bni.co.id/promo/detail/test-1")
    assert not c._allowed_by_robots("https://bniexperience.bni.co.id/sliders")
    assert not c._allowed_by_robots("https://bniexperience.bni.co.id/promo/preview/abc")
    assert not c._allowed_by_robots("https://www.bni.co.id/id-id/")


def _mock_bni_transport() -> httpx.MockTransport:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /\nDisallow: /sliders\nDisallow: /promo/preview/*\n",
            )
        if url in (
            "https://bniexperience.bni.co.id/promo",
            "https://bniexperience.bni.co.id/promo/surabaya",
        ):
            return httpx.Response(200, text=listing)
        if url == expected["detail_1"]["source_url"]:
            return httpx.Response(200, text=detail_1)
        if url == expected["detail_2"]["source_url"]:
            return httpx.Response(200, text=detail_2)
        return httpx.Response(404, text="Not found")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_via_mock_transport() -> None:
    c = BankBNIConnector(transport=_mock_bni_transport())
    c.rate_limit_per_second = 0
    c.max_retries = 0
    items = await c.fetch(limit=20)
    assert len(items) == 2
    urls = [item.source_url for item in items]
    assert any("oppo-find" in u for u in urls)
    assert any("nusantara-tour-travel" in u for u in urls)


@pytest.mark.asyncio
async def test_health_check_via_mock_transport() -> None:
    c = BankBNIConnector(transport=_mock_bni_transport())
    c.rate_limit_per_second = 0
    health = await c.health_check()
    assert health.ok is True
    assert health.source_id == "bni"
    assert health.items_found == 20
    assert health.last_success_at is not None
