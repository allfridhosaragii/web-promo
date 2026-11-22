"""Test konektor BCA — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from datetime import UTC
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.bank_bca import (
    BankBCAConnector,
    extract_detail_fields,
    extract_promo_links,
    parse_sitemap_locs,
)
from connectors.base import canonical_url
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "bca"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert links == expected["listing_links"]
    # JANGAN fetch /search (Disallow di robots.txt promo.bca.co.id).
    assert not any("/search" in u for u in links)


def test_detail_1_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_1"]
    html = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("value_amount") == expected["value_amount"]
    assert extracted.get("max_discount") == expected["max_discount"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_detail_2_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_2"]
    html = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted.get("min_purchase") == expected["min_purchase"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_parse_sitemap_index_and_urlset() -> None:
    idx_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://promo.bca.co.id/1/sitemap.xml</loc></sitemap>
    </sitemapindex>"""
    children, pages = parse_sitemap_locs(idx_xml)
    assert children == ["https://promo.bca.co.id/1/sitemap.xml"]
    assert pages == []


def test_canonical_url_strips_tracking() -> None:
    assert (
        canonical_url("https://promo.bca.co.id/id/x?utm_source=a&__cf_chl_tk=1")
        == "https://promo.bca.co.id/id/x"
    )


def test_connector_defaults_and_parse() -> None:
    c = BankBCAConnector()
    assert c.source_id == "bca"
    assert c.rate_limit_per_second == 1.0
    assert c.max_retries == 2
    item = c.make_raw_item(source_url="https://promo.bca.co.id/id/all/2026/11/x", text="  promo  ")
    parsed = c.parse(item)
    assert parsed.text == "promo"
    assert parsed.fetched_at is not None and parsed.fetched_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_robots_disallow_search() -> None:
    c = BankBCAConnector()
    c._robots = c._robots_parser("User-agent: *\nAllow: /\nDisallow: /*/search\n", c.base_url)
    assert c._allowed_by_robots("https://promo.bca.co.id/id/all/2026/11/16/09/HUAWEI-Principle")
    assert not c._allowed_by_robots("https://promo.bca.co.id/id/search?q=kopi")
