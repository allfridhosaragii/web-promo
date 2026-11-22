"""Test konektor AZKO — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.azko import AzkoConnector, extract_detail_fields, extract_promo_links
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "azko"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert links == expected["listing_links"]


def test_detail_1_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_1"]
    html = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("value_percent") == expected["value_percent"]
    assert extracted.get("min_purchase") == expected["min_purchase"]
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


def test_robots_disallow_api_and_hc() -> None:
    c = AzkoConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /hc\nDisallow: /detail_receipt/\n",
        "https://azko.id/",
    )
    assert c._allowed_by_robots("https://azko.id/promo/christmas-extra-deals")
    assert not c._allowed_by_robots("https://azko.id/api/promos")
    assert not c._allowed_by_robots("https://azko.id/hc/faq")
    assert not c._allowed_by_robots("https://azko.id/detail_receipt/123")


def _mock_azko_transport() -> httpx.MockTransport:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\nDisallow: /api/\n")
        if url == "https://azko.id/promo":
            return httpx.Response(200, text=listing)
        if url == expected["detail_1"]["source_url"]:
            return httpx.Response(200, text=detail_1)
        if url == expected["detail_2"]["source_url"]:
            return httpx.Response(200, text=detail_2)
        return httpx.Response(404, text="Not found")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_via_mock_transport() -> None:
    c = AzkoConnector(transport=_mock_azko_transport())
    c.rate_limit_per_second = 0
    c.max_retries = 0
    items = await c.fetch(limit=10)
    assert len(items) == 2
    urls = [item.source_url for item in items]
    assert "https://azko.id/promo/christmas-extra-deals" in urls
    assert "https://azko.id/promo/payday-surprise" in urls


@pytest.mark.asyncio
async def test_health_check_via_mock_transport() -> None:
    c = AzkoConnector(transport=_mock_azko_transport())
    c.rate_limit_per_second = 0
    c.max_retries = 0
    health = await c.health_check()
    assert health.ok is True
    assert health.source_id == "azko"
    assert health.items_found == 5
    assert health.last_success_at is not None
