"""Test dokumen Meilisearch — Unix ts + lifecycle/moderation (ARCH §5.2, A2/A4)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.index import should_index, to_meilisearch_doc, to_unix_ts


def _promo(**overrides):
    promo = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Diskon 50% Kopi",
        "summary": "Kopi diskon setengah harga.",
        "brand_name": "Kopi SBY",
        "brand_slug": "kopi-sby",
        "platform": "Kopi SBY",
        "promo_type": "persen",
        "value_percent": 50,
        "voucher_code": "KOPI50",
        "category_slugs": ["makanan-minuman"],
        "region_scope": "nasional",
        "starts_at": datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 11, 30, 16, 59, 59, tzinfo=UTC),
        "lifecycle": "aktif",
        "moderation": "terverifikasi",
        "confidence": 0.9,
        "source_url": "https://example.test/promo",
        "is_seed": False,
    }
    promo.update(overrides)
    return promo


def test_unix_ts_conversion() -> None:
    assert to_unix_ts(datetime(2026, 11, 30, 16, 59, 59, tzinfo=UTC)) == 1796057999
    assert to_unix_ts("2026-11-30T16:59:59Z") == 1796057999
    assert to_unix_ts(None) is None
    assert to_unix_ts("bukan-tanggal") is None


def test_doc_has_ts_fields_and_no_status() -> None:
    doc = to_meilisearch_doc(_promo())
    assert doc["starts_at_ts"] == int(datetime(2026, 11, 1, tzinfo=UTC).timestamp())
    assert doc["ends_at_ts"] == 1796057999
    assert doc["starts_at"] == "2026-11-01T00:00:00+00:00"  # ISO hanya tampilan
    assert doc["lifecycle"] == "aktif"
    assert doc["moderation"] == "terverifikasi"
    assert "status" not in doc  # kolom tunggal lama dihapus di v2


def test_doc_open_ended_has_null_ends_ts() -> None:
    doc = to_meilisearch_doc(_promo(ends_at=None))
    assert doc["ends_at"] is None
    assert doc["ends_at_ts"] is None


def test_should_index_rule() -> None:
    assert should_index(_promo()) is True
    assert should_index(_promo(lifecycle="segera_berakhir")) is True
    assert should_index(_promo(lifecycle="kedaluwarsa")) is False
    assert should_index(_promo(lifecycle="dijadwalkan")) is False
    assert should_index(_promo(moderation="ditolak")) is False
    assert should_index(_promo(moderation="dilaporkan")) is True  # dilaporkan tetap tampil
    assert should_index(_promo(is_seed=True)) is False
