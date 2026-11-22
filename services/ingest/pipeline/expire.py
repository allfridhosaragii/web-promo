"""Aturan expire & recurring — ARCHITECTURE.md §5.3. Satu sumber kebenaran.

- segera_berakhir = ends_at < 24 jam dari sekarang (WIB).
- Promo berulang: ends_at adalah akhir periode SAAT INI; expire job membuat
  kemunculan berikutnya dari recurring_rule, bukan menghapus promo.
- TTL raw_items = 30 hari.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
SOON_THRESHOLD = timedelta(hours=24)
RAW_ITEMS_TTL = timedelta(days=30)


def compute_status(
    starts_at: datetime | None, ends_at: datetime | None, now: datetime | None = None
) -> str:
    """Hitung status dari tanggal. now harus aware (UTC); default now UTC."""
    now = now or datetime.now(UTC)
    if ends_at is not None and now >= ends_at:
        return "kedaluwarsa"
    if ends_at is not None and ends_at - now < SOON_THRESHOLD:
        return "segera_berakhir"
    if starts_at is not None and now < starts_at:
        return "belum_terverifikasi"
    return "aktif"


def normalize_end_of_day_wib(day: datetime) -> datetime:
    """Tanggal tanpa jam ("s.d. 30 Nov") -> 23:59:59 WIB hari itu, kembalikan UTC."""
    wib_day = day.astimezone(WIB).replace(hour=23, minute=59, second=59, microsecond=0)
    return wib_day.astimezone(UTC)


def next_weekly_occurrence(ends_at: datetime, byday: list[int]) -> datetime:
    """Kemunculan berikutnya untuk FREQ=WEEKLY;BYDAY. byday: 0=Senin..6=Minggu (Python).
    Contoh JSM: BYDAY=FRI,SAT,SUN -> [4,5,6], ends_at Minggu 23:59 WIB ->
    kembalikan Minggu berikutnya 23:59 WIB (akhir periode berikutnya)."""
    candidate = ends_at + timedelta(days=1)
    while candidate.weekday() not in byday:
        candidate += timedelta(days=1)
    # Akhir periode = hari BYDAY terakhir pada minggu kemunculan itu, 23:59:59 WIB.
    last_day = max(byday)
    while candidate.weekday() != last_day:
        candidate += timedelta(days=1)
    wib = candidate.astimezone(WIB).replace(hour=23, minute=59, second=59, microsecond=0)
    return wib.astimezone(UTC)


def raw_item_expired(fetched_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return now - fetched_at > RAW_ITEMS_TTL
