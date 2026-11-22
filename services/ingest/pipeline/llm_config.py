"""Konfigurasi LLM — SATU-SATUNYA tempat limit & model dibaca (ARCH §11.1).

JANGAN hardcode nama model atau angka RPD di kode lain: semuanya dibaca dari
.env lewat sini. Model TIDAK ditentukan dokumen — owner memilih sendiri model
free tier dengan RPD terbesar yang tampil di AI Studio proyeknya:

  1. Buka https://aistudio.google.com/ -> Rate Limits (proyek BuruPromo).
  2. Pilih model free tier dengan RPD terbesar (mis. Flash-Lite terbaru).
  3. Isi .env: LLM_MODEL, LLM_RPM, LLM_DAILY_REQUEST_LIMIT, LLM_TPM
     dengan angka yang tampil di sana. Catat juga ke docs/adr/ + /admin.

Default di bawah ini adalah FALLBACK TERBURUK (bacaan 21 Okt 2026 untuk
2.5 Flash-Lite: 10 RPM / 250rb TPM / 20 RPD) — dipakai bila .env kosong,
supaya desain tidak pernah mengasumsikan kuota besar. Default BUKAN janji
Google: batas free tier bervariasi per proyek dan tidak dijamin.

Tanpa LLM_MODEL (kosong) -> TIDAK ADA panggilan LLM sama sekali, pipeline
memakai ekstraksi aturan + antrean review manual. Tanpa billing account,
tidak ada jalur yang bisa menimbulkan tagihan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    # Nama model persis seperti di AI Studio, mis. "gemini-2.5-flash-lite".
    # Kosong = LLM nonaktif (aturan saja).
    model: str = ""
    rpm: int = 10  # fallback terburuk; isi dari AI Studio
    daily_request_limit: int = 20  # fallback terburuk (RPD); isi dari AI Studio
    tpm: int = 250_000  # fallback terburuk; isi dari AI Studio

    @classmethod
    def from_env(cls, env: dict | None = None) -> LLMConfig:
        src = env if env is not None else os.environ

        def _int(key: str, default: int) -> int:
            try:
                return int(str(src.get(key, "") or default))
            except ValueError:
                return default

        return cls(
            model=str(src.get("LLM_MODEL", "") or "").strip(),
            rpm=_int("LLM_RPM", 10),
            daily_request_limit=_int("LLM_DAILY_REQUEST_LIMIT", 20),
            tpm=_int("LLM_TPM", 250_000),
        )

    def to_status(self) -> dict:
        return {
            "model": self.model or None,
            "rpm": self.rpm,
            "daily_request_limit": self.daily_request_limit,
            "tpm": self.tpm,
            "billing": "none — free tier, tanpa billing account",
        }
