"""Interface LLM ekstraksi — Gemini 2.5 Flash-Lite FREE TIER via Google AI Studio.

Revisi 2 + perbaikan B (ARCH §11.1, ADR 0004 — menggantikan budget guard, ADR 0003):
- Proyek Google Cloud BuruPromo TIDAK BOLEH punya billing account. Tanpa
  billing, tidak ada jalur yang bisa menimbulkan tagihan: API yang melebihi
  free tier hanya mengembalikan 429, bukan menagih.
- TIDAK ADA fallback berbayar. GPT-4o-mini dihapus sebagai fallback.
  Pengganti LLM harus free tier lain yang disetujui owner dulu.
- Model TIDAK dikunci di kode: owner memilih model free tier dengan RPD
  terbesar yang tampil di AI Studio proyeknya, disimpan di .env (LLM_MODEL).
  Limit dibaca dari pipeline/llm_config.py (.env: LLM_MODEL, LLM_RPM,
  LLM_DAILY_REQUEST_LIMIT, LLM_TPM). JANGAN hardcode nama model / RPD di sini.
- Kuota dihitung dalam JUMLAH REQUEST, bukan rupiah. Reset tengah malam
  waktu Pasifik (00:00 PT).
- Kena 429 (RPD habis) -> job berhenti, sisa masuk llm_queue (Redis di
  produksi, list in-memory di sini), diproses ulang setelah reset PT.
- Ekstraksi berbasis aturan (pipeline/rules.py) jalan DULU; LLM hanya untuk
  field yang tidak bisa diparse aturan. Hasil di-cache per content_hash.
- Tanpa GEMINI_API_KEY atau tanpa LLM_MODEL, TIDAK ADA panggilan API — hasil
  aturan dikembalikan dengan needs_review=True bila field wajib kosong.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline.llm_config import LLMConfig
from pipeline.rules import extract_rules, needs_llm

PT = ZoneInfo("America/Los_Angeles")

# Nama antrean (Redis di produksi). Satu-satunya tempat nama ini didefinisikan.
LLM_QUEUE_KEY = "llm_queue"


def _is_429(exc: Exception) -> bool:
    """True bila exception adalah rate limit 429 dari Gemini (google-genai
    melempar APIError dengan atribut `.code`, atau pesan berisi '429')."""
    code = getattr(exc, "code", None)
    if code is not None:
        try:
            return int(code) == 429
        except (TypeError, ValueError):
            pass
    return "429" in str(exc)


class QuotaExhaustedError(RuntimeError):
    """Kuota harian (RPD) habis — tidak ada retry hari ini."""


class RateLimitedError(RuntimeError):
    """Kena 429 sesaat (RPM/TPM) — retry dengan backoff, maks 3x."""


@dataclass
class QuotaGuard:
    """Pelacak kuota LLM free tier. Job WAJIB cek sebelum tiap panggilan.

    Limit dibaca dari LLMConfig (.env) bila tidak diisi eksplisit — TIDAK ADA
    angka hardcode di sini. `clock` bisa di-inject di test.
    """

    daily_limit: int | None = None
    rpm_limit: int | None = None
    requests_today: int = 0
    exhausted_today: bool = False
    clock: Callable[[], datetime] | None = None
    _day_pt: date | None = None
    _minute_calls: list[datetime] = field(default_factory=list)
    queued: list[dict] = field(default_factory=list)  # llm_queue (in-memory; Redis di prod)

    def __post_init__(self) -> None:
        config = LLMConfig.from_env()
        if self.daily_limit is None:
            self.daily_limit = config.daily_request_limit
        if self.rpm_limit is None:
            self.rpm_limit = config.rpm

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

    Model + limit dari LLMConfig (.env) — TIDAK dikunci ke satu model.
    Tanpa GEMINI_API_KEY atau tanpa LLM_MODEL -> tidak ada panggilan.
    Kuota habis -> hasil aturan + item masuk llm_queue.
    Panggilan LLM nyata memakai SDK baru `google-genai` (google-generativeai
    sudah deprecated dan DIHAPUS dari dependensi): `from google import genai`,
    `client.models.generate_content` dengan `response_mime_type="application/json"`
    + `response_schema`. LLM hanya MENGISI field yang belum didapat aturan —
    tidak pernah menimpa field aturan, tidak pernah mengarang.
    """

    config: LLMConfig = field(default_factory=LLMConfig.from_env)
    guard: QuotaGuard = field(default_factory=QuotaGuard)
    cache: dict[str, ExtractionResult] = field(default_factory=dict)

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def api_key(self) -> str | None:
        return os.environ.get("GEMINI_API_KEY") or None

    async def extract(self, text: str, content_hash: str | None = None) -> ExtractionResult:
        key = content_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self.cache:
            cached = self.cache[key]
            return ExtractionResult(
                fields=cached.fields,
                source="cache",
                llm_used=cached.llm_used,
                needs_review=cached.needs_review,
                note="cache content_hash",
            )

        rules = extract_rules(text)
        if not needs_llm(rules):
            result = ExtractionResult(fields=rules, source="rules")
            self.cache[key] = result
            return result

        if not self.api_key or not self.config.model:
            missing = "GEMINI_API_KEY" if not self.api_key else "LLM_MODEL"
            return ExtractionResult(
                fields=rules,
                source="rules",
                needs_review=True,
                note=f"{missing} belum diisi — tidak ada panggilan API. "
                "Isi dari AI Studio proyek owner (ARCH §11.1). "
                "Field yang kurang masuk antrean review manual.",
            )

        try:
            self.guard.check()
        except QuotaExhaustedError as exc:
            self.guard.enqueue({"content_hash": key, "text": text})
            return ExtractionResult(
                fields=rules,
                source="rules",
                needs_review=True,
                queued=True,
                note=str(exc),
            )
        except RateLimitedError as exc:
            return ExtractionResult(
                fields=rules,
                source="rules",
                needs_review=True,
                note=f"{exc} Item tidak diantrekan — retry oleh scheduler dengan backoff.",
            )

        # Kuota tersedia + API key + model ada -> panggil Gemini (google-genai).
        try:
            llm_fields = self._call_gemini(text)
        except RateLimitedError:
            return ExtractionResult(
                fields=rules,
                source="rules",
                needs_review=True,
                note="Gemini 429 — retry oleh scheduler dengan backoff. "
                "Item tidak diantrekan; quota guard sudah mencatat request ini.",
            )
        except Exception as exc:  # noqa: BLE001 — kegagalan LLM tidak boleh mematikan pipeline
            return ExtractionResult(
                fields=rules,
                source="rules",
                needs_review=True,
                note=f"Panggilan Gemini gagal ({exc}) — dipakai hasil aturan saja, "
                "masuk antrean review manual.",
            )
        self.guard.record()
        merged = {**llm_fields, **rules}  # aturan menang; LLM hanya mengisi yang kosong
        result = ExtractionResult(fields=merged, source="rules+llm", llm_used=True)
        self.cache[key] = result
        return result

    def _call_gemini(self, text: str) -> dict:
        """Satu request Gemini via SDK `google-genai`. Import lazy supaya modul
        ini tetap bisa diimpor tanpa SDK (test aturan tidak butuh API key).

        Mengembalikan dict field hasil parse JSON. Raise RateLimitedError bila
        respons 429. Test memakai stub client via monkeypatch sys.modules
        (lihat pipeline/tests/test_llm_genai.py) — tanpa request live.
        """
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        schema = {
            "type": "OBJECT",
            "properties": {
                "value_percent": {"type": "NUMBER"},
                "value_amount": {"type": "NUMBER"},
                "max_discount": {"type": "NUMBER"},
                "min_purchase": {"type": "NUMBER"},
                "voucher_code": {"type": "STRING"},
                "promo_type": {"type": "STRING"},
                "ends_at": {"type": "STRING"},
                "recurring_rule": {"type": "STRING"},
            },
        }
        prompt = (
            "Ekstrak info promo dari teks berikut dan kembalikan JSON sesuai skema. "
            "Jangan mengarang field yang tidak ada di teks (isi null). "
            "ends_at dalam format ISO 8601 dengan zona +07:00 bila ada tanggal berakhir.\n\n"
            f"{text}"
        )
        try:
            response = client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                ),
            )
        except Exception as exc:
            if _is_429(exc):
                self.guard.note_429()
                raise RateLimitedError(
                    "Gemini mengembalikan 429 (RPM/TPM/RPD). "
                    "Retry dengan backoff (2/4/8 dtk, maks 3x); bila RPD habis, "
                    "job berhenti dan sisa masuk llm_queue setelah reset PT."
                ) from exc
            raise
        parsed = json.loads(response.text or "{}")
        return parsed if isinstance(parsed, dict) else {}
