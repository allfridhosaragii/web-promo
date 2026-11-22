"""Interface LLM ekstraksi — Gemini 2.5 Flash-Lite FREE TIER via Google AI Studio.

Revisi 2 (ARCH §11.1, ADR 0004 — menggantikan budget guard $5/bulan, ADR 0003):
- Proyek Google Cloud BuruPromo TIDAK BOLEH punya billing account. Tanpa
  billing, tidak ada jalur yang bisa menimbulkan tagihan: API yang melebihi
  free tier hanya mengembalikan 429, bukan menagih.
- TIDAK ADA fallback berbayar. GPT-4o-mini dihapus sebagai fallback.
  Pengganti LLM harus free tier lain yang disetujui owner dulu.
- Kuota dihitung dalam JUMLAH REQUEST, bukan rupiah:
  LLM_DAILY_REQUESTS (default 20 = bacaan terburuk 2.5 Flash-Lite 20 RPD,
  21 Okt 2026 — JANGAN hardcode 1000), LLM_RPM (default 10).
  Reset tengah malam waktu Pasifik (00:00 PT).
- Kena 429 (RPD habis) -> job berhenti, sisa masuk llm_queue (Redis di
  produksi, list in-memory di sini), diproses ulang setelah reset PT.
- Ekstraksi berbasis aturan (pipeline/rules.py) jalan DULU; LLM hanya untuk
  field yang tidak bisa diparse aturan. Hasil di-cache per content_hash.
- Tanpa GEMINI_API_KEY, TIDAK ADA panggilan API — hasil aturan dikembalikan
  dengan needs_review=True bila field wajib kosong.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline.rules import extract_rules, needs_llm

PT = ZoneInfo("America/Los_Angeles")

# Batas free tier — bacaan terburuk, bukan janji Google (ARCH §11.1).
# Verifikasi di AI Studio proyek owner sendiri sebelum vertical slice.
DAILY_REQUESTS = int(os.environ.get("LLM_DAILY_REQUESTS", "20"))
RPM_LIMIT = int(os.environ.get("LLM_RPM", "10"))
MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")

# Nama antrean (Redis di produksi). Satu-satunya tempat nama ini didefinisikan.
LLM_QUEUE_KEY = "llm_queue"


class QuotaExhaustedError(RuntimeError):
    """Kuota harian (RPD) habis — tidak ada retry hari ini."""


class RateLimitedError(RuntimeError):
    """Kena 429 sesaat (RPM/TPM) — retry dengan backoff, maks 3x."""


@dataclass
class QuotaGuard:
    """Pelacak kuota LLM free tier. Job WAJIB cek sebelum tiap panggilan.

    `clock` bisa di-inject di test (fungsi -> datetime UTC sadar zona).
    """

    daily_limit: int = DAILY_REQUESTS
    rpm_limit: int = RPM_LIMIT
    requests_today: int = 0
    exhausted_today: bool = False
    clock: Callable[[], datetime] | None = None
    _day_pt: date | None = None
    _minute_calls: list[datetime] = field(default_factory=list)
    queued: list[dict] = field(default_factory=list)  # llm_queue (in-memory; Redis di prod)

    def _now(self) -> datetime:
        return self.clock() if self.clock else datetime.now(UTC)

    def _rollover(self) -> bool:
        """Reset hitungan saat hari berganti (tengah malam PT). True bila reset terjadi."""
        today = self._now().astimezone(PT).date()
        if self._day_pt != today:
            self._day_pt = today
            self.requests_today = 0
            self.exhausted_today = False
            return True
        return False

    def reset_at(self) -> datetime:
        """Tengah malam PT berikutnya, dalam UTC."""
        now_pt = self._now().astimezone(PT)
        midnight = datetime(now_pt.year, now_pt.month, now_pt.day, tzinfo=PT) + timedelta(days=1)
        return midnight.astimezone(UTC)

    @property
    def remaining_today(self) -> int:
        self._rollover()
        return max(0, self.daily_limit - self.requests_today)

    def _rpm_used(self) -> int:
        cutoff = self._now() - timedelta(minutes=1)
        self._minute_calls = [t for t in self._minute_calls if t > cutoff]
        return len(self._minute_calls)

    def can_call(self) -> bool:
        self._rollover()
        return (
            not self.exhausted_today
            and self.requests_today < self.daily_limit
            and self._rpm_used() < self.rpm_limit
        )

    def check(self) -> None:
        """Raise bila tidak boleh panggil sekarang. Dipanggil sebelum tiap request LLM."""
        self._rollover()
        if self.exhausted_today or self.requests_today >= self.daily_limit:
            raise QuotaExhaustedError(
                f"Kuota LLM harian habis: {self.requests_today}/{self.daily_limit} request "
                f"(reset {self.reset_at().isoformat()} UTC = tengah malam PT). "
                "Sisa item masuk llm_queue, diproses ulang setelah reset — tanpa tagihan."
            )
        if self._rpm_used() >= self.rpm_limit:
            raise RateLimitedError(
                f"Rate limit sesaat: {self.rpm_limit} request/menit tercapai. "
                "Retry dengan backoff (2/4/8 dtk, maks 3x)."
            )

    def record(self) -> None:
        """Catat SATU request LLM yang benar-benar terkirim. Panggil setelah HTTP 200/429."""
        self._rollover()
        self.requests_today += 1
        self._minute_calls.append(self._now())

    def note_429(self, daily: bool = False) -> None:
        """Catat respons 429 dari Gemini. daily=True = RPD habis (berhenti hari ini)."""
        self.record()
        if daily:
            self.exhausted_today = True

    def enqueue(self, item: dict) -> None:
        """Sisa item masuk llm_queue — diproses ulang setelah reset PT."""
        self.queued.append(item)

    def drain_after_reset(self) -> list[dict]:
        """Kembalikan antrean bila hari sudah berganti (reset terjadi)."""
        if self._rollover() and self.queued:
            items, self.queued = self.queued, []
            return items
        return []

    def status(self) -> dict:
        self._rollover()
        return {
            "model": MODEL,
            "used_today": self.requests_today,
            "remaining_today": self.remaining_today,
            "daily_limit": self.daily_limit,
            "rpm_limit": self.rpm_limit,
            "reset_at_utc": self.reset_at().isoformat(),
            "queued_count": len(self.queued),
            "exhausted_today": self.exhausted_today,
            # Rp0: tidak ada biaya, tidak ada billing account — field ini sengaja
            # tidak ada (spent_usd dihapus bersama BudgetGuard, ADR 0004).
            "billing": "none — free tier, tanpa billing account",
        }


@dataclass
class ExtractionResult:
    fields: dict
    source: str  # "rules" | "rules+llm" | "cache"
    llm_used: bool = False
    needs_review: bool = False
    queued: bool = False
    note: str = ""


@dataclass
class LLMExtractor:
    """Ekstraksi: aturan dulu, LLM hanya bila perlu, cache per content_hash.

    Tanpa GEMINI_API_KEY -> tidak ada panggilan, hasil aturan dikembalikan.
    Kuota habis -> hasil aturan + item masuk llm_queue.
    Panggilan LLM nyata (google-generativeai, JSON Schema) di vertical slice BCA.
    """

    model: str = MODEL
    guard: QuotaGuard = field(default_factory=QuotaGuard)
    cache: dict[str, ExtractionResult] = field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        return os.environ.get("GEMINI_API_KEY") or None

    async def extract(self, text: str, content_hash: str | None = None) -> ExtractionResult:
        key = content_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self.cache:
            cached = self.cache[key]
            return ExtractionResult(
                fields=cached.fields, source="cache", llm_used=cached.llm_used,
                needs_review=cached.needs_review, note="cache content_hash",
            )

        rules = extract_rules(text)
        if not needs_llm(rules):
            result = ExtractionResult(fields=rules, source="rules")
            self.cache[key] = result
            return result

        if not self.api_key:
            return ExtractionResult(
                fields=rules, source="rules", needs_review=True,
                note="GEMINI_API_KEY belum diisi — tidak ada panggilan API. "
                "Field yang kurang masuk antrean review manual (ARCH §11.1).",
            )

        try:
            self.guard.check()
        except QuotaExhaustedError as exc:
            self.guard.enqueue({"content_hash": key, "text": text})
            return ExtractionResult(
                fields=rules, source="rules", needs_review=True, queued=True,
                note=str(exc),
            )
        except RateLimitedError as exc:
            return ExtractionResult(
                fields=rules, source="rules", needs_review=True,
                note=f"{exc} Item tidak diantrekan — retry oleh scheduler dengan backoff.",
            )

        # Kuota tersedia + API key ada, tapi panggilan nyata belum diimplementasi
        # (vertical slice BCA). Jangan record() — belum ada request terkirim.
        raise NotImplementedError(
            "LLMExtractor.extract (panggilan Gemini) diimplementasikan di vertical slice BCA. "
            "Sampai saat itu, hanya hasil aturan yang dipakai."
        )
