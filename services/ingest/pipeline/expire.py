"""Aturan expire & recurring — ARCHITECTURE.md §5.3. Satu sumber kebenaran.

- lifecycle: dijadwalkan | aktif | segera_berakhir | kedaluwarsa (dihitung dari tanggal).
- moderation: belum_ditinjau | terverifikasi | dilaporkan | ditolak (diputuskan
  manusia/komunitas — BUKAN dari tanggal; lihat packages/db schema).
- segera_berakhir = ends_at < 24 jam dari sekarang (WIB).
- Promo berulang: recurring_rule adalah RRULE valid (RFC 5545) — kode BYDAY
  yang benar: MO TU WE TH FR SA SU (bukan SAT/SUN/FRI). JSM =
  FREQ=WEEKLY;BYDAY=FR,SA,SU. Jumat = FREQ=WEEKLY;BYDAY=FR. Payday =
  FREQ=MONTHLY;BYMONTHDAY=25. Diparse dengan dateutil.rrule.
- Promo TANPA ends_at: label "Tanpa batas waktu", wajib recheck tiap 6 jam,
  auto-kedaluwarsa bila tidak terkonfirmasi selama 14 hari (last_confirmed_at).
- TTL raw_items = 30 hari.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from dateutil.rrule import rrulestr

WIB = timezone(timedelta(hours=7))
SOON_THRESHOLD = timedelta(hours=24)
RAW_ITEMS_TTL = timedelta(days=30)
UNCONFIRMED_MAX_AGE = timedelta(days=14)  # tanpa ends_at + tak terkonfirmasi
RECHECK_OPEN_ENDED = timedelta(hours=6)  # promo tanpa ends_at: recheck tiap 6 jam
RECHECK_WITH_ENDS_AT = timedelta(hours=24)

# Kode BYDAY RRULE yang valid (RFC 5545). SAT/SUN/FRI BUKAN kode yang benar.
_WEEKDAY_CODE = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_BYDAY_RE = re.compile(r"BYDAY=([A-Z,]+)")
_FREQ_RE = re.compile(r"FREQ=([A-Z]+)")


def compute_lifecycle(
    starts_at: datetime | None,
    ends_at: datetime | None,
    now: datetime | None = None,
    last_confirmed_at: datetime | None = None,
) -> str:
    """Hitung lifecycle dari tanggal. now harus aware (UTC); default now UTC.

    Tanpa ends_at -> "Tanpa batas waktu": tetap aktif selama terkonfirmasi,
    auto-kedaluwarsa bila last_confirmed_at lebih dari 14 hari.
    """
    now = now or datetime.now(UTC)
    if ends_at is not None and now >= ends_at:
        return "kedaluwarsa"
    if ends_at is None and last_confirmed_at is not None:
        if now - last_confirmed_at > UNCONFIRMED_MAX_AGE:
            return "kedaluwarsa"
    if ends_at is not None and ends_at - now < SOON_THRESHOLD:
        return "segera_berakhir"
    if starts_at is not None and now < starts_at:
        return "dijadwalkan"
    return "aktif"


def compute_status(
    starts_at: datetime | None, ends_at: datetime | None, now: datetime | None = None
) -> str:
    """Alias lama (deprecated) — pakai compute_lifecycle. Dipertahankan supaya
    pemanggil lama tidak pecah; nilainya SAMA dengan lifecycle."""
    return compute_lifecycle(starts_at, ends_at, now)


def is_open_ended(ends_at: datetime | None) -> bool:
    """Promo tanpa ends_at -> tampil 'Tanpa batas waktu' di web/kontrak."""
    return ends_at is None


def normalize_end_of_day_wib(day: datetime) -> datetime:
    """Tanggal tanpa jam ("s.d. 30 Nov") -> 23:59:59 WIB hari itu, kembalikan UTC."""
    wib_day = day.astimezone(WIB).replace(hour=23, minute=59, second=59, microsecond=0)
    return wib_day.astimezone(UTC)


def _end_of_day_wib(day: datetime) -> datetime:
    return normalize_end_of_day_wib(day)


def _last_byday_in_week(day: datetime, byday: list[int]) -> datetime:
    """Hari BYDAY terakhir pada minggu (Senin-Minggu) yang memuat `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday + timedelta(days=max(byday))


def next_weekly_occurrence(ends_at: datetime, byday: list[int]) -> datetime:
    """Kemunculan berikutnya untuk FREQ=WEEKLY;BYDAY. byday: 0=Senin..6=Minggu.
    Contoh JSM: BYDAY=FR,SA,SU -> [4,5,6], ends_at Minggu 23:59 WIB ->
    kembalikan Minggu berikutnya 23:59 WIB (akhir periode berikutnya)."""
    from dateutil.rrule import WEEKLY, rrule

    rule = rrule(WEEKLY, dtstart=ends_at, byweekday=byday)
    nxt = rule.after(ends_at, inc=False)
    if nxt is None:  # pragma: no cover — rrule WEEKLY tanpa COUNT selalu ada
        raise ValueError("rrule WEEKLY tidak menghasilkan kemunculan berikutnya")
    end_day = _last_byday_in_week(nxt, byday)
    return _end_of_day_wib(end_day)


def next_recurring_ends(recurring_rule: str, current_ends_at: datetime) -> datetime | None:
    """Kemunculan berikutnya dari RRULE valid. Kembalikan ends_at baru
    (23:59:59 WIB di hari terakhir periode itu) atau None bila rule invalid /
    tidak ada kemunculan berikutnya. Jangan tebak pola — None = antrean manual."""
    try:
        rule = rrulestr(recurring_rule, dtstart=current_ends_at)
    except Exception:
        return None
    nxt = rule.after(current_ends_at, inc=False)
    if nxt is None:
        return None
    freq = (_FREQ_RE.search(recurring_rule) or [None, ""])[1]
    if freq == "WEEKLY":
        byday_match = _BYDAY_RE.search(recurring_rule)
        if byday_match:
            codes = [c for c in byday_match.group(1).split(",") if c in _WEEKDAY_CODE]
            if codes:
                byday = [_WEEKDAY_CODE[c] for c in codes]
                return _end_of_day_wib(_last_byday_in_week(nxt, byday))
    return _end_of_day_wib(nxt)


def recheck_due(
    last_checked_at: datetime | None, ends_at: datetime | None, now: datetime | None = None
) -> bool:
    """Apakah promo sudah waktunya dicek ulang ke sumber?
    Tanpa ends_at: tiap 6 jam (lebih sering — tidak ada tanggal yang membuktikan
    promo masih berlaku). Dengan ends_at: tiap 24 jam, atau tiap 1 jam bila
    segera berakhir (< 24 jam)."""
    now = now or datetime.now(UTC)
    if last_checked_at is None:
        return True
    if ends_at is None:
        return now - last_checked_at > RECHECK_OPEN_ENDED
    if ends_at - now < SOON_THRESHOLD:
        return now - last_checked_at > timedelta(hours=1)
    return now - last_checked_at > RECHECK_WITH_ENDS_AT


def raw_item_expired(fetched_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return now - fetched_at > RAW_ITEMS_TTL
