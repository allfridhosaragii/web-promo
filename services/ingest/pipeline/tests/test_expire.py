"""Test logika expire & recurring murni — ARCHITECTURE.md §5.3."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.expire import compute_status, next_weekly_occurrence, raw_item_expired


def test_segera_berakhir_under_24h() -> None:
    now = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
    assert compute_status(None, datetime(2026, 11, 23, 9, 0, tzinfo=UTC), now) == "segera_berakhir"
    assert compute_status(None, datetime(2026, 11, 25, 10, 0, tzinfo=UTC), now) == "aktif"
    assert compute_status(None, datetime(2026, 11, 22, 9, 0, tzinfo=UTC), now) == "kedaluwarsa"
    assert (
        compute_status(
            datetime(2026, 11, 25, 0, 0, tzinfo=UTC), datetime(2026, 11, 30, 0, 0, tzinfo=UTC), now
        )
        == "belum_terverifikasi"
    )


def test_jsm_next_occurrence_is_next_sunday() -> None:
    # JSM: ends Minggu 2026-11-22 23:59 WIB. Kemunculan berikut: Minggu 2026-11-29 23:59 WIB.
    ends = datetime(2026, 11, 22, 16, 59, 59, tzinfo=UTC)  # = 23:59:59 WIB
    nxt = next_weekly_occurrence(ends, [4, 5, 6])
    assert nxt == datetime(2026, 11, 29, 16, 59, 59, tzinfo=UTC)


def test_raw_items_ttl_30_days() -> None:
    now = datetime(2026, 11, 22, 0, 0, tzinfo=UTC)
    assert raw_item_expired(datetime(2026, 10, 20, 0, 0, tzinfo=UTC), now) is True
    assert raw_item_expired(datetime(2026, 11, 1, 0, 0, tzinfo=UTC), now) is False
