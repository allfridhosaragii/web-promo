"""Ekstraksi berbasis aturan (regex) — jalan SEBELUM LLM (ARCH §11.1, §3.3).

Alasan: Gemini free tier sangat kecil (bacaan terburuk 20 request/hari).
Aturan dulu → LLM hanya untuk field yang tidak bisa diparse aturan.
Field yang tidak ditemukan = tidak ada di dict (None di Pydantic),
BUKAN tebakan. Tanggal dinormalisasi ke 23:59:59 WIB bila hanya tanggal.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")

_BULAN = {
    "jan": 1,
    "januari": 1,
    "feb": 2,
    "februari": 2,
    "mar": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "agu": 8,
    "aug": 8,
    "agustus": 8,
    "sep": 9,
    "september": 9,
    "okt": 10,
    "oct": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "des": 12,
    "dec": 12,
    "desember": 12,
}

_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})(?:\s+([A-Za-z]+))?(?:\s+(\d{4}))?\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"(?:s\.?\s*d\.?|sampai|hingga|berakhir|berlaku\s+(?:sampai|hingga)?|sd\.?)\s+"
    r"(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
_DATE_BARE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d{1,3})\s*(?:%|persen)", re.IGNORECASE)
_DISCOUNT_AMOUNT_RE = re.compile(
    r"(?:diskon|potongan|hemat|cashback)(?:\s+hingga)?\s+(?:rp|idr)\s*([\d.,]+)\s*(rb|ribu|jt|juta)?",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"(?:rp|idr)\s*([\d.,]+)\s*(rb|ribu|jt|juta)?", re.IGNORECASE)
_MIN_PURCHASE_RE = re.compile(
    r"(?:min(?:imal)?\.?|minimum)\s*(?:belanja|pembelian|transaksi)?\s*"
    r"(?:rp\s*)?([\d.,]+)\s*(rb|ribu|jt|juta)?",
    re.IGNORECASE,
)
_MAX_DISCOUNT_RE = re.compile(
    r"(?:maks(?:imal)?\.?|max\.?)\s*(?:diskon|potongan)?\s*(?:rp\s*)?([\d.,]+)\s*(rb|ribu|jt|juta)?",
    re.IGNORECASE,
)
_VOUCHER_RE = re.compile(
    r"(?:kode(?:\s*voucher|\s*promo)?|voucher(?:\s*code|\s*kode)?)\s*[:\-]?\s*([A-Z0-9]{4,20})",
    re.IGNORECASE,
)
_VOUCHER_STOPWORDS = {"GAME", "PROMO", "DISKON", "GRATIS", "BELANJA", "MAKAN", "VOUCHER"}
_CASHBACK_PERCENT_RE = re.compile(r"cashback\s+(\d{1,3})\s*(?:%|persen)", re.IGNORECASE)


def _parse_amount(raw: str, suffix: str | None) -> int | None:
    """'15.000' -> 15000, '15' + 'rb' -> 15000, '1.5' + 'juta' -> 1500000."""
    suf = suffix.lower() if suffix else ""
    if suf in ("jt", "juta"):
        try:
            return round(float(raw.replace(",", ".")) * 1_000_000)
        except ValueError:
            return None
    try:
        value = int(raw.replace(".", "").replace(",", ""))
    except ValueError:
        return None
    if suf in ("rb", "ribu"):
        value *= 1000
    return value


def _parse_date(day: str, month_name: str, year: str | None, now: datetime) -> datetime | None:
    month = _BULAN.get(month_name.lower())
    if month is None:
        return None
    year_int = int(year) if year else now.astimezone(WIB).year
    try:
        # 23:59:59 WIB di hari itu -> UTC (WIB = UTC+7).
        local = datetime(year_int, month, int(day), 23, 59, 59, tzinfo=WIB)
    except ValueError:
        return None
    return local.astimezone(UTC)


def extract_rules(text: str, now: datetime | None = None) -> dict:
    """Parse teks promo dengan regex. Hanya field yang ditemukan yang dikembalikan."""
    now = now or datetime.now(UTC)
    out: dict = {}
    low = text.lower()

    # --- tanggal mulai & berakhir ---
    rm = _DATE_RANGE_RE.search(text)
    if rm:
        starts = _parse_date(
            rm.group(1), rm.group(2) or rm.group(5), rm.group(3) or rm.group(6), now
        )
        if starts is not None:
            # starts_at dimulai 00:00:00 WIB hari tersebut
            out["starts_at"] = (
                starts.astimezone(WIB)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .astimezone(UTC)
            )
        ends = _parse_date(rm.group(4), rm.group(5), rm.group(6), now)
        if ends is not None:
            out["ends_at"] = ends
    else:
        m = _DATE_RE.search(text) or _DATE_BARE_RE.search(text)
        if m:
            ends = _parse_date(
                m.group(1),
                m.group(2),
                m.group(3) if m.lastindex and m.lastindex >= 3 else None,
                now,
            )
            if ends is not None:
                out["ends_at"] = ends

    # --- batas diskon / minimal belanja (ekstrak dulu agar tidak tertukar value_amount) ---
    mx = _MAX_DISCOUNT_RE.search(text)
    if mx:
        amount = _parse_amount(mx.group(1), mx.group(2))
        if amount is not None:
            out["max_discount"] = amount
    mn = _MIN_PURCHASE_RE.search(text)
    if mn:
        amount = _parse_amount(mn.group(1), mn.group(2))
        if amount is not None:
            out["min_purchase"] = amount

    # --- tipe + nilai ---
    if "gratis ongkir" in low or "bebas ongkir" in low or "ongkir 0" in low:
        out["promo_type"] = "gratis_ongkir"
    elif "cashback" in low:
        out["promo_type"] = "cashback"
        cm = _CASHBACK_PERCENT_RE.search(text)
        if cm and float(cm.group(1)) > 0:
            out["value_percent"] = float(cm.group(1))
        else:
            cleaned = _MIN_PURCHASE_RE.sub("", text)
            am = _AMOUNT_RE.search(cleaned)
            if am:
                amount = _parse_amount(am.group(1), am.group(2))
                if amount is not None:
                    out["value_amount"] = amount
    else:
        # Prioritaskan diskon nominal eksplisit jika judul/teks menyebut "diskon hingga Rp..."
        dam = _DISCOUNT_AMOUNT_RE.search(text)
        pm = next((m for m in _PERCENT_RE.finditer(text) if float(m.group(1)) > 0), None)
        if pm and (not dam or pm.start() < dam.start()):
            out["promo_type"] = "persen"
            out["value_percent"] = float(pm.group(1))
        elif dam:
            out["promo_type"] = "potongan_nominal"
            amount = _parse_amount(dam.group(1), dam.group(2))
            if amount is not None:
                out["value_amount"] = amount
        else:
            # Cari Rp... di luar teks minimal belanja
            cleaned = _MIN_PURCHASE_RE.sub("", text)
            am = _AMOUNT_RE.search(cleaned)
            if am:
                out["promo_type"] = "potongan_nominal"
                amount = _parse_amount(am.group(1), am.group(2))
                if amount is not None:
                    out["value_amount"] = amount
            elif "harga spesial" in low or "menu spesial" in low:
                out["promo_type"] = "harga_spesial"
            elif "cicilan" in low and "0%" in low:
                out["promo_type"] = "cicilan_0"

    # --- kode voucher ---
    vm = _VOUCHER_RE.search(text)
    if vm and vm.group(1).upper() not in _VOUCHER_STOPWORDS:
        out["voucher_code"] = vm.group(1).upper()

    # --- pola berulang eksplisit: JSM = Jumat–Minggu (ARCH §5.3) ---
    # Kode BYDAY RRULE yang benar: FR,SA,SU (bukan FRI/SAT/SUN).
    if re.search(r"\bjsm\b", low) or "jumat sabtu minggu" in low:
        out["recurring_rule"] = "FREQ=WEEKLY;BYDAY=FR,SA,SU"

    return out


def needs_llm(partial: dict) -> bool:
    """LLM hanya dipanggil bila nilai promo ATAU tanggal berakhir belum ketemu aturan."""
    has_value = (
        "value_percent" in partial
        or "value_amount" in partial
        or partial.get("promo_type") == "gratis_ongkir"
    )
    return not (has_value and "ends_at" in partial)
