"""Test konektor OVO — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.ovo import OvoConnector, extract_detail_fields, extract_promo_links
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "ovo"


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
    assert extracted["starts_at"].astimezone(WIB).isoformat() == expected["starts_at_wib"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_detail_2_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_2"]
    html = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("value_percent") == expected["value_percent"]
    assert extracted.get("min_purchase") == expected["min_purchase"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["starts_at"].astimezone(WIB).isoformat() == expected["starts_at_wib"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_robots_disallow_query_and_page() -> None:
    c = OvoConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nDisallow: */page/*\nDisallow: */?*\n",
        "https://ovo.id/",
    )
    assert c._allowed_by_robots("https://ovo.id/deals/view/42710")
    assert not c._allowed_by_robots("https://ovo.id/deals/view/42710?utm_source=x")
    assert not c._allowed_by_robots("https://ovo.id/deals/page/2")
    assert not c._allowed_by_robots("https://other.example/deals/view/42710")


@pytest.mark.asyncio
async def test_fetch_and_health_check_with_mock_transport() -> None:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: */page/*\nDisallow: */?*\n")
        if url == "https://ovo.id/deals":
            return httpx.Response(200, text="<html>ok</html>")
        if url == expected["detail_1"]["source_url"]:
            return httpx.Response(200, text=detail_1)
        if url == expected["detail_2"]["source_url"]:
            return httpx.Response(200, text=detail_2)
        return httpx.Response(404, text="Not found")

    async def fake_listing_fetcher(url: str) -> str:
        assert url == "https://ovo.id/deals"
        return listing

    c = OvoConnector(transport=httpx.MockTransport(handler), html_fetcher=fake_listing_fetcher)
    c.max_retries = 0
    c.rate_limit_per_second = 0

    items = await c.fetch(limit=9)
    assert len(items) == 2
    assert items[0].source_url == expected["detail_1"]["source_url"]
    assert items[0].title == expected["detail_1"]["title"]
    assert items[1].source_url == expected["detail_2"]["source_url"]
    assert items[1].title == expected["detail_2"]["title"]

    parsed = c.parse(items[0])
    assert parsed.title == expected["detail_1"]["title"]

    health = await c.health_check()
    assert health.ok is True
