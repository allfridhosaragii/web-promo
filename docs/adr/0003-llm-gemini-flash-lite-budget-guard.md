# ADR 0003 — LLM Gemini 2.5 Flash-Lite + budget guard

- Status: **SUPERSEDED oleh ADR 0004 (2026-11-22, revisi 2)**
- Alasan: keputusan owner berubah menjadi SEMUA GRATIS (Rp0). Budget guard
  berbasis USD dihapus seluruhnya — diganti quota guard berbasis jumlah
  request (tanpa billing account, tanpa jalur tagihan). Jangan pakai ADR ini
  sebagai rujukan; baca ADR 0004.

- Isi asli (arsip, tidak berlaku):
- Konteks: Ekstraksi terstruktur butuh LLM murah & cepat dengan JSON Schema.
- Keputusan (lama): Google Gemini 2.5 Flash-Lite via Google AI Studio.
  Budget maks per bulan, cap harian, peringatan, job berhenti otomatis
  di 100%. Tanpa GEMINI_API_KEY, tidak ada panggilan berbayar — antrean manual.
  Interface `pipeline/llm.py` bisa diganti provider (fallback: GPT-4o-mini).
- X API: budget $0, disabled sampai Fase 2.
