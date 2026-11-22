"""Test quota guard LLM free tier + ekstraksi aturan dulu (ARCH §11.1, ADR 0004).

Revisi 2: TIDAK ADA budget USD. Batas = jumlah request (default 20/hari, 10/menit),
reset tengah malam PT. Kena 429 (RPD) -> antre llm_queue, proses ulang setelah reset.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.llm import (
    LLMExtractor,
    QuotaExhaustedError,
    QuotaGuard,
    RateLimitedError,
)
from pipeline.rules import extract_rules, needs_llm


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now_value = start

    def __call__(self) -> datetime:
        return self.now_value

    def advance(self, **kwargs) -> None:
        self.now_value += timedelta(**kwargs)


def _guard(**kwargs) -> tuple[QuotaGuard, FakeClock]:
    # 2026-11-22 10:00 UTC = 02:00 PT (hari yang sama).
    clock = FakeClock(datetime(2026, 11, 22, 10, 0, tzinfo=UTC))
    return QuotaGuard(clock=clock, **kwargs), clock


def test_default_limits_are_worst_case_20_per_day_10_per_minute() -> None:
    g = QuotaGuard()
    assert g.daily_limit == 20, "default HARUS 20 (bacaan terburuk), bukan 1000"
    assert g.rpm_limit == 10


def test_guard_blocks_at_daily_cap_and_resets_after_midnight_pt() -> None:
    g, clock = _guard(daily_limit=2, rpm_limit=10)
    g.record()
    g.record()
    assert g.can_call() is False
    with pytest.raises(QuotaExhaustedError):
        g.check()
    assert g.remaining_today == 0
    # Maju ke 08:30 UTC hari berikutnya = 00:30 PT -> hari baru, kuota reset.
    clock.advance(hours=22, minutes=30)
    assert g.can_call() is True
    assert g.remaining_today == 2


def test_guard_blocks_on_rpm_then_recovers_after_a_minute() -> None:
    g, clock = _guard(daily_limit=20, rpm_limit=2)
    g.record()
    g.record()
    with pytest.raises(RateLimitedError):
        g.check()
    clock.advance(seconds=61)
    assert g.can_call() is True


def test_429_daily_marks_exhausted_and_queues_item() -> None:
    g, clock = _guard(daily_limit=20, rpm_limit=10)
    g.note_429(daily=True)
    assert g.exhausted_today is True
    assert g.can_call() is False
    g.enqueue({"content_hash": "abc", "text": "Diskon 50%"})
    assert len(g.queued) == 1
    assert g.status()["queued_count"] == 1
    # Belum reset -> drain kosong.
    assert g.drain_after_reset() == []
    clock.advance(hours=22, minutes=30)
    assert g.drain_after_reset() == [{"content_hash": "abc", "text": "Diskon 50%"}]
    assert g.queued == []


def test_status_has_no_usd_fields() -> None:
    g, _ = _guard(daily_limit=20, rpm_limit=10)
    status = g.status()
    assert "spent" not in str(status).lower() and "usd" not in str(status).lower()
    assert status["billing"] == "none — free tier, tanpa billing account"


def test_rules_extract_percent_code_and_end_date() -> None:
    text = "Diskon 50% kopi, kode: KOPI50, s.d. 30 Nov 2026. Min. belanja Rp50.000."
    out = extract_rules(text)
    assert out["value_percent"] == 50.0
    assert out["promo_type"] == "persen"
    assert out["voucher_code"] == "KOPI50"
    assert out["min_purchase"] == 50000
    # 30 Nov 2026 23:59:59 WIB = 16:59:59 UTC.
    assert out["ends_at"] == datetime(2026, 11, 30, 16, 59, 59, tzinfo=UTC)
    assert needs_llm(out) is False


def test_rules_extract_amount_and_jsm_recurring() -> None:
    out = extract_rules("Potongan Rp15.000, JSM di Indomaret, berlaku s.d. 22 Nov 2026.")
    assert out["value_amount"] == 15000
    assert out["recurring_rule"] == "FREQ=WEEKLY;BYDAY=FRI,SAT,SUN"
    out2 = extract_rules("Gratis ongkir tanpa minimal belanja")
    assert out2["promo_type"] == "gratis_ongkir"
    assert needs_llm(out2) is True  # tanpa tanggal berakhir -> LLM/review masih perlu


def test_rules_never_invent_missing_fields() -> None:
    out = extract_rules("Promo menarik di toko kami, jangan lewatkan!")
    assert out == {}
    assert needs_llm(out) is True


@pytest.mark.asyncio
async def test_extractor_rules_first_no_key_no_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ex = LLMExtractor()
    res = await ex.extract("Diskon 50% kopi, s.d. 30 Nov 2026.")
    assert res.llm_used is False
    assert res.source == "rules"
    assert res.needs_review is False
    assert res.fields["value_percent"] == 50.0


@pytest.mark.asyncio
async def test_extractor_without_key_returns_rules_with_needs_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ex = LLMExtractor()
    res = await ex.extract("Promo kopi enak sekali, datang dan coba!")
    assert res.llm_used is False
    assert res.needs_review is True
    assert "GEMINI_API_KEY" in res.note


@pytest.mark.asyncio
async def test_extractor_caches_by_content_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ex = LLMExtractor()
    first = await ex.extract("Diskon 50% kopi, s.d. 30 Nov 2026.", content_hash="h1")
    second = await ex.extract("teks lain sama sekali", content_hash="h1")
    assert second.source == "cache"
    assert second.fields == first.fields


@pytest.mark.asyncio
async def test_extractor_quota_exhausted_queues_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-untuk-test")
    guard, _ = _guard(daily_limit=1, rpm_limit=10)
    guard.record()  # kuota 1/hari habis
    ex = LLMExtractor(guard=guard)
    res = await ex.extract("Promo kopi, datang saja!")
    assert res.queued is True
    assert res.needs_review is True
    assert len(guard.queued) == 1
