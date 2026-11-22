"""Test wiring SDK baru `google-genai` di pipeline/llm.py (ARCH §11.1, ADR 0004).

SDK lama `google-generativeai` sudah deprecated dan dihapus dari dependensi.
Test ini memakai stub client lewat sys.modules — TANPA request live ke Gemini.
"""

from __future__ import annotations

import json
import sys
import types as pytypes
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.llm import LLMExtractor


class _FakeConfig:
    """Menangkap kwargs GenerateContentConfig."""

    last_kwargs: dict | None = None

    def __init__(self, **kwargs) -> None:
        _FakeConfig.last_kwargs = kwargs


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(
        self,
        text: str = '{"value_percent": 25.0, "voucher_code": "HEMAT25"}',
        exc: Exception | None = None,
    ) -> None:
        self._text = text
        self._exc = exc
        self.last_call: dict | None = None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._text)


class _FakeClient:
    last_models: _FakeModels | None = None

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.models = _FakeModels()
        _FakeClient.last_models = self.models


def _install_fake_genai(
    monkeypatch,
    exc: Exception | None = None,
    text: str = '{"value_percent": 25.0, "voucher_code": "HEMAT25"}',
):
    """Pasang stub google.genai + google.genai.types di sys.modules."""
    fake_types = pytypes.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = _FakeConfig
    fake_genai = pytypes.ModuleType("google.genai")
    fake_genai.Client = _FakeClient

    def _client_factory(api_key=None):
        client = _FakeClient(api_key=api_key)
        client.models = _FakeModels(text=text, exc=exc)
        _FakeClient.last_models = client.models
        return client

    fake_genai.Client = _client_factory
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)


def _extractor(monkeypatch) -> LLMExtractor:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-bukan-asli")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setenv("LLM_DAILY_REQUEST_LIMIT", "20")
    monkeypatch.setenv("LLM_RPM", "10")
    return LLMExtractor()


def test_call_gemini_uses_new_sdk_with_json_schema(monkeypatch) -> None:
    _install_fake_genai(monkeypatch)
    ex = _extractor(monkeypatch)
    out = ex._call_gemini("Diskon kopi 25%")
    assert out == {"value_percent": 25.0, "voucher_code": "HEMAT25"}
    call = _FakeClient.last_models.last_call
    assert call["model"] == "gemini-2.5-flash-lite"
    assert _FakeConfig.last_kwargs["response_mime_type"] == "application/json"
    assert "value_percent" in _FakeConfig.last_kwargs["response_schema"]["properties"]


@pytest.mark.asyncio
async def test_extract_merges_llm_fields_without_overwriting_rules(monkeypatch) -> None:
    _install_fake_genai(monkeypatch, text='{"max_discount": 100000, "voucher_code": "HEMAT25"}')
    ex = _extractor(monkeypatch)
    # Teks ini butuh LLM (tidak ada tanggal berakhir -> needs_llm True),
    # tapi aturan sudah dapat persen + kode dari teks.
    result = await ex.extract("Diskon 50% kopi, kode: KOPI50")
    assert result.llm_used is True
    assert result.source == "rules+llm"
    assert result.fields["value_percent"] == 50.0  # aturan menang
    assert result.fields["voucher_code"] == "KOPI50"  # aturan menang atas LLM
    assert result.fields["max_discount"] == 100000  # LLM mengisi yang kosong


class _Err429(Exception):
    code = 429


@pytest.mark.asyncio
async def test_extract_429_returns_rules_without_crashing(monkeypatch) -> None:
    _install_fake_genai(monkeypatch, exc=_Err429("429 Resource exhausted"))
    ex = _extractor(monkeypatch)
    result = await ex.extract("Promo menarik di toko kami, jangan lewatkan!")
    assert result.llm_used is False
    assert result.needs_review is True
    assert "429" in result.note
    assert json.dumps(result.fields)  # fields tetap JSON-serializable


@pytest.mark.asyncio
async def test_extract_with_custom_base_url_and_api_key(monkeypatch) -> None:
    import httpx

    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {"message": {"content": '{"value_percent": 30, "voucher_code": "KUSTOM30"}'}}
                ]
            },
        )

    monkeypatch.setenv("LLM_API_KEY", "sk-custom-test")
    monkeypatch.setenv("LLM_BASE_URL", "https://custom-llm.example/v1/")
    monkeypatch.setenv("LLM_MODEL", "custom-model-v1")
    monkeypatch.setattr(httpx, "post", fake_post)

    ex = LLMExtractor()
    result = await ex.extract("Promo spesial makan siang tanpa tanggal")
    assert result.llm_used is True
    assert captured["url"] == "https://custom-llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-custom-test"
    assert captured["json"]["model"] == "custom-model-v1"
    assert result.fields["voucher_code"] == "KUSTOM30"
