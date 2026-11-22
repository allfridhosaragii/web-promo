"""Test konektor BCA — HANYA dari fixture lokal, TIDAK ADA request live (ARCH §12.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.bank_bca import BankBCAConnector, extract_links
from connectors.base import canonical_url

FIXTURES = Path(__file__).parent / "fixtures" / "bca"


def test_fixture_files_exist() -> None:
    for name in ("listing.html", "detail-1.html", "detail-2.html", "expected.json"):
        assert (FIXTURES / name).exists(), f"fixture hilang: {name}"


def test_listing_links_from_fixture() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text())
    links = [canonical_url(u) for u in extract_links((FIXTURES / "listing.html").read_text())]
    assert links == expected["listing_links"]
    # JANGAN fetch /search (Disallow di robots.txt promo.bca.co.id).
    assert not any("/search" in u for u in links)


def test_canonical_url_strips_tracking() -> None:
    assert (
        canonical_url("https://promo.bca.co.id/id/x?utm_source=a&__cf_chl_tk=1")
        == "https://promo.bca.co.id/id/x"
    )


def test_connector_defaults() -> None:
    c = BankBCAConnector()
    assert c.source_id == "bca"
    assert c.rate_limit_per_second == 1.0
    assert c.max_retries == 2


@pytest.mark.asyncio
async def test_fetch_disabled_in_phase_0() -> None:
    c = BankBCAConnector()
    with pytest.raises(NotImplementedError):
        await c.fetch()
    health = await c.health_check()
    assert health.ok is False
