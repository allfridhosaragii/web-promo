"""Test konektor CIMB Niaga — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.cimb import (
    CimbConnector,
    extract_detail_fields,
    extract_promo_links_from_sitemap,
)
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "cimb"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_sitemap_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links_from_sitemap(
        (FIXTURES / "listing.html").read_text(encoding="utf-8")
    )
    assert len(links) >= 700
    for sample in expected["listing_sample_links"]:
        assert sample in links


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


def test_robots_disallow_aem_paths() -> None:
    c = CimbConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nDisallow: /cgi-bin/\nDisallow: /_jcr_content/*\n",
        "https://www.cimbniaga.co.id/",
    )
    assert c._allowed_by_robots(
        "https://www.cimbniaga.co.id/id/personal/promo/promo-detail.PRM-141026-00001"
    )
    assert not c._allowed_by_robots("https://www.cimbniaga.co.id/cgi-bin/test")
    assert not c._allowed_by_robots("https://www.cimbniaga.co.id/_jcr_content/foo")
    assert not c._allowed_by_robots("https://other.example/id/personal/promo/promo-detail.1")


@pytest.mark.asyncio
async def test_fetch_and_health_check_with_mock_transport() -> None:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /cgi-bin/\n")
        if url == "https://www.cimbniaga.co.id/sitemap/promo.xml":
            return httpx.Response(200, text=listing)
        if url == expected["detail_1"]["source_url"]:
            return httpx.Response(200, text=detail_1)
        if url == expected["detail_2"]["source_url"]:
            return httpx.Response(200, text=detail_2)
        return httpx.Response(404, text="Not found")

    c = CimbConnector(transport=httpx.MockTransport(handler))
    c.max_retries = 0
    c.rate_limit_per_second = 0

    items = await c.fetch(limit=5)
    assert len(items) == 2
    assert items[0].source_url == expected["detail_1"]["source_url"]
    assert items[0].title == expected["detail_1"]["title"]
    assert items[1].source_url == expected["detail_2"]["source_url"]
    assert items[1].title == expected["detail_2"]["title"]

    parsed = c.parse(items[0])
    assert parsed.title == expected["detail_1"]["title"]

    health = await c.health_check()
    assert health.ok is True
    assert health.items_found >= 700
