"""Test logika expire & recurring murni — ARCHITECTURE.md §5.3.

Perbaikan A3/A4/A5: RRULE valid (BYDAY=FR,SA,SU — bukan SAT/SUN),
lifecycle terpisah dari moderation, promo tanpa ends_at ("Tanpa batas waktu").
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.expire import (
    compute_lifecycle,
    compute_status,
    is_open_ended,
    next_recurring_ends,
    next_weekly_occurrence,
    raw_item_expired,
    recheck_due,
)


def test_segera_berakhir_under_24h() -> None:
    now = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
    assert (
        compute_lifecycle(None, datetime(2026, 11, 23, 9, 0, tzinfo=UTC), now) == "segera_berakhir"
    )
    assert compute_lifecycle(None, datetime(2026, 11, 25, 10, 0, tzinfo=UTC), now) == "aktif"
    assert compute_lifecycle(None, datetime(2026, 11, 22, 9, 0, tzinfo=UTC), now) == "kedaluwarsa"
    assert (
        compute_lifecycle(
            datetime(2026, 11, 25, 0, 0, tzinfo=UTC), datetime(2026, 11, 30, 0, 0, tzinfo=UTC), now
        )
        == "dijadwalkan"  # dulu "belum_terverifikasi" — sekarang lifecycle terpisah (A4)
    )
    # Alias lama tetap mengembalikan nilai lifecycle yang sama.
    assert compute_status(None, datetime(2026, 11, 25, 10, 0, tzinfo=UTC), now) == "aktif"


def test_jsm_next_occurrence_is_next_sunday() -> None:
    # JSM: ends Minggu 2026-11-22 23:59 WIB. Kemunculan berikut: Minggu 2026-11-29 23:59 WIB.
    ends = datetime(2026, 11, 22, 16, 59, 59, tzinfo=UTC)  # = 23:59:59 WIB
    nxt = next_weekly_occurrence(ends, [4, 5, 6])
    assert nxt == datetime(2026, 11, 29, 16, 59, 59, tzinfo=UTC)


def test_rrule_jsm_valid_codes() -> None:
    # RRULE valid: FREQ=WEEKLY;BYDAY=FR,SA,SU (SAT/SUN/FRI TIDAK valid).
    ends = datetime(2026, 11, 22, 16, 59, 59, tzinfo=UTC)  # Minggu 23:59 WIB
    nxt = next_recurring_ends("FREQ=WEEKLY;BYDAY=FR,SA,SU", ends)
    assert nxt == datetime(2026, 11, 29, 16, 59, 59, tzinfo=UTC)


def test_rrule_friday_weekly_and_payday_monthly() -> None:
    friday = datetime(2026, 11, 20, 16, 59, 59, tzinfo=UTC)  # Jumat 23:59 WIB
    assert next_recurring_ends("FREQ=WEEKLY;BYDAY=FR", friday) == datetime(
        2026, 11, 27, 16, 59, 59, tzinfo=UTC
    )
    payday = datetime(2026, 11, 25, 16, 59, 59, tzinfo=UTC)  # 25 Nov 23:59 WIB
    assert next_recurring_ends("FREQ=MONTHLY;BYMONTHDAY=25", payday) == datetime(
        2026, 12, 25, 16, 59, 59, tzinfo=UTC
    )


def test_rrule_invalid_returns_none_not_guess() -> None:
    ends = datetime(2026, 11, 22, 16, 59, 59, tzinfo=UTC)
    assert next_recurring_ends("FREQ=WEEKLY;BYDAY=SAT,SUN", ends) is None
    assert next_recurring_ends("bukan-rrule", ends) is None
    assert next_recurring_ends("", ends) is None


def test_open_ended_auto_expires_after_14_days_unconfirmed() -> None:
    now = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
    assert is_open_ended(None) is True
    assert is_open_ended(datetime(2026, 11, 30, tzinfo=UTC)) is False
    confirmed_recent = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    assert compute_lifecycle(None, None, now, confirmed_recent) == "aktif"
    confirmed_old = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)  # 15 hari lalu
    assert compute_lifecycle(None, None, now, confirmed_old) == "kedaluwarsa"
    # Tepat 14 hari masih aktif (batas: LEBIH dari 14 hari).
    confirmed_edge = now - timedelta(days=14)
    assert compute_lifecycle(None, None, now, confirmed_edge) == "aktif"


def test_recheck_due_open_ended_more_frequent() -> None:
    now = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
    assert recheck_due(None, None, now) is True
    checked_5h = now - timedelta(hours=5)
    assert recheck_due(checked_5h, None, now) is False
    assert recheck_due(now - timedelta(hours=7), None, now) is True
    # Dengan ends_at: baru due setelah 24 jam (kecuali segera berakhir).
    checked_23h = now - timedelta(hours=23)
    assert recheck_due(checked_23h, datetime(2026, 12, 1, tzinfo=UTC), now) is False
    assert (
        recheck_due(now - timedelta(hours=2), datetime(2026, 11, 22, 20, 0, tzinfo=UTC), now)
        is True
    )


def test_raw_items_ttl_30_days() -> None:
    now = datetime(2026, 11, 22, 0, 0, tzinfo=UTC)
    assert raw_item_expired(datetime(2026, 10, 20, 0, 0, tzinfo=UTC), now) is True
    assert raw_item_expired(datetime(2026, 11, 1, 0, 0, tzinfo=UTC), now) is False
