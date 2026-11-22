"""Test konektor GoPay — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.gopay import (
    GoPayConnector,
    extract_detail_fields,
    extract_promo_links,
    parse_sitemap_urls,
)
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "gopay"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert links == expected["listing_links"]
    assert not any("?page" in u or "?category" in u for u in links)


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
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_parse_sitemap_urls() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://gopay.co.id/promo/tiket</loc></url>
      <url><loc>https://gopay.co.id/promo/alfamart</loc></url>
    </urlset>"""
    assert parse_sitemap_urls(xml) == [
        "https://gopay.co.id/promo/tiket",
        "https://gopay.co.id/promo/alfamart",
    ]


def test_robots_disallow_page_and_category_queries() -> None:
    c = GoPayConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nAllow: /\nDisallow: /promo?page\nDisallow: /promo?category\nDisallow: /id/\n",
        "https://gopay.co.id/",
    )
    assert c._allowed_by_robots("https://gopay.co.id/promo/tiket")
    assert not c._allowed_by_robots("https://gopay.co.id/promo?page=2")
    assert not c._allowed_by_robots("https://gopay.co.id/promo?category=fnb")
    assert not c._allowed_by_robots("https://gopay.co.id/id/promo/tiket")


def _mock_gopay_transport() -> httpx.MockTransport:
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://gopay.co.id/promo/tiket</loc></url>
      <url><loc>https://gopay.co.id/promo/alfamart</loc></url>
      <url><loc>https://gopay.co.id/promo?page=2</loc></url>
    </urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\nDisallow: /promo?page\n")
        if url.endswith("/sitemap-promo.xml"):
            return httpx.Response(200, text=sitemap)
        if url.endswith("/promo/tiket"):
            return httpx.Response(200, text=detail_1)
        if url.endswith("/promo/alfamart"):
            return httpx.Response(200, text=detail_2)
        return httpx.Response(404, text="Not found")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_via_mock_transport() -> None:
    c = GoPayConnector(transport=_mock_gopay_transport())
    c.rate_limit_per_second = 0
    items = await c.fetch(limit=10)
    assert len(items) == 2
    urls = [item.source_url for item in items]
    assert "https://gopay.co.id/promo/tiket" in urls
    assert "https://gopay.co.id/promo/alfamart" in urls
    assert not any("?page=" in u for u in urls)


@pytest.mark.asyncio
async def test_health_check_via_mock_transport() -> None:
    c = GoPayConnector(transport=_mock_gopay_transport())
    c.rate_limit_per_second = 0
    health = await c.health_check()
    assert health.ok is True
    assert health.source_id == "gopay"
    assert health.items_found == 3
    assert health.last_success_at is not None
