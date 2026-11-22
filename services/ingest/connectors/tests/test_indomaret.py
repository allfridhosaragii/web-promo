"""Test konektor Indomaret — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.indomaret import (
    IndomaretConnector,
    extract_detail_fields,
    extract_promo_sections,
)
from pipeline.rules import WIB, extract_rules

FIXTURES = Path(__file__).parent / "fixtures" / "indomaret"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_sections_from_listing_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    sections = extract_promo_sections((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    assert [title for title, _ in sections] == expected["section_titles"]


def test_detail_1_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_1"]
    html = (FIXTURES / "detail-1.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted["starts_at"].astimezone(WIB).isoformat() == expected["starts_at_wib"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_detail_2_extraction_matches_expected() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["detail_2"]
    html = (FIXTURES / "detail-2.html").read_text(encoding="utf-8")
    title, text = extract_detail_fields(html)
    assert title == expected["title"]
    extracted = extract_rules(text)
    assert extracted["promo_type"] == expected["promo_type"]
    assert extracted["starts_at"].astimezone(WIB).isoformat() == expected["starts_at_wib"]
    assert extracted["ends_at"].astimezone(WIB).isoformat() == expected["ends_at_wib"]


def test_scope_restricts_to_indomaret_promosi() -> None:
    c = IndomaretConnector()
    assert c._allowed_by_robots("https://www.indomaret.co.id/promosi/")
    assert not c._allowed_by_robots("https://www.indomaret.co.id/other")
    assert not c._allowed_by_robots("https://other.example/promosi/")


@pytest.mark.asyncio
async def test_fetch_and_health_check_with_mock_transport() -> None:
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://www.indomaret.co.id/promosi/":
            return httpx.Response(200, text=listing)
        return httpx.Response(404, text="Not found")

    c = IndomaretConnector(transport=httpx.MockTransport(handler))
    c.max_retries = 0
    c.rate_limit_per_second = 0

    items = await c.fetch(limit=20)
    assert len(items) == len(expected["section_titles"])
    assert items[0].title == "Super Hemat"
    assert items[0].source_url == "https://www.indomaret.co.id/promosi?section=super-hemat"

    parsed = c.parse(items[0])
    assert parsed.title == "Super Hemat"

    health = await c.health_check()
    assert health.ok is True
    assert health.items_found == len(expected["section_titles"])
