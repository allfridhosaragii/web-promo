"""Test konektor Informa — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.informa import InformaConnector, extract_detail_fields, extract_promo_links
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "informa"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    links = extract_promo_links((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert links == expected["listing_links"]


def test_listing_skips_undefined_and_external() -> None:
    html = """
    <html><body>
      <a href="/home-promotion/undefined">Broken</a>
      <a href="https://example.com/home-promotion/fake">External</a>
      <a href="/home-promotion">Root</a>
      <a href="/home-promotion/valid-promo?utm_source=x">Valid</a>
    </body></html>
    """
    assert extract_promo_links(html) == ["https://informa.co.id/home-promotion/valid-promo"]


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
    assert extracted.get("value_percent") == expected["value_percent"]
    assert extracted.get("min_purchase") == expected["min_purchase"]
    assert extracted.get("voucher_code") == expected["voucher_code"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_robots_disallow_up_and_undefined() -> None:
    c = InformaConnector()
    c._robots = c._robots_parser(
        "User-agent: *\nAllow: /\nDisallow: /up\n", "https://informa.co.id/"
    )
    assert c._allowed_by_robots(
        "https://informa.co.id/home-promotion/informa-electronics-black-friday"
    )
    assert not c._allowed_by_robots("https://informa.co.id/up/health")
    assert not c._allowed_by_robots("https://informa.co.id/home-promotion/undefined")
    assert not c._allowed_by_robots("https://other.example/home-promotion/x")


@pytest.mark.asyncio
async def test_fetch_with_mock_fetcher() -> None:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail_1 = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    detail_2 = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def robots_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\nDisallow: /up\n")
        return httpx.Response(200, text="<html>ok</html>")

    async def fake_fetcher(url: str) -> str:
        if url == "https://informa.co.id/home-promotion":
            return listing
        if url == expected["detail_1"]["source_url"]:
            return detail_1
        if url == expected["detail_2"]["source_url"]:
            return detail_2
        raise httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url), response=httpx.Response(404)
        )

    c = InformaConnector(transport=httpx.MockTransport(robots_handler), html_fetcher=fake_fetcher)
    c.max_retries = 0
    c.rate_limit_per_second = 0

    items = await c.fetch(limit=6)
    assert len(items) == 2
    assert items[0].source_url == expected["detail_1"]["source_url"]
    assert items[0].title == expected["detail_1"]["title"]
    assert items[1].source_url == expected["detail_2"]["source_url"]
    assert items[1].title == expected["detail_2"]["title"]

    parsed = c.parse(items[0])
    assert parsed.title == expected["detail_1"]["title"]

    health = await c.health_check()
    assert health.ok is True
