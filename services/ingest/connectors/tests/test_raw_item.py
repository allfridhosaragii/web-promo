"""Test RawItem — dataclass kw_only (ARCH §5.1, perbaikan A1).

Regresi: field wajib `text` pernah berisiko tertukar dengan field ber-default.
kw_only=True memaksa konstruksi pakai keyword, jadi urutan tidak bisa salah.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from connectors.base import RawItem


def test_raw_item_keyword_construction() -> None:
    item = RawItem(source_id="bca", source_url="https://promo.bca.co.id/x", text="Diskon 50%")
    assert item.source_id == "bca"
    assert item.text == "Diskon 50%"
    assert item.title is None
    assert item.media_urls == []
    assert item.content_hash is None


def test_raw_item_positional_construction_rejected() -> None:
    # kw_only=True: konstruksi posisional harus gagal — jangan diam-diam tertukar.
    with pytest.raises(TypeError):
        RawItem("bca", "https://promo.bca.co.id/x", "Diskon 50%")  # type: ignore[call-arg]


def test_raw_item_is_frozen() -> None:
    item = RawItem(source_id="bca", source_url="https://promo.bca.co.id/x", text="Diskon 50%")
    with pytest.raises(FrozenInstanceError):
        item.text = "diubah"  # type: ignore[misc]
