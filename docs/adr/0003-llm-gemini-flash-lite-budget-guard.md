# ADR 0003 — LLM Gemini 2.5 Flash-Lite + budget guard $5/bulan

- Status: Diterima (keputusan owner 2026-11-22)
- Konteks: Ekstraksi terstruktur butuh LLM murah & cepat dengan JSON Schema.
- Keputusan: Google Gemini 2.5 Flash-Lite via Google AI Studio.
  Budget maks $5/bulan, cap harian $0,16, peringatan $4, job berhenti otomatis
  di 100%. Tanpa GEMINI_API_KEY, tidak ada panggilan berbayar — antrean manual.
  Interface `pipeline/llm.py` bisa diganti provider (fallback: GPT-4o-mini).
- X API: budget $0, disabled sampai Fase 2.
