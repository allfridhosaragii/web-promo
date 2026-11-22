# ADR 0004 — LLM Gemini free tier + quota guard (tanpa billing)

- Status: Diterima (keputusan owner 2026-11-22, revisi 2)
- Menggantikan: **ADR 0003 (SUPERSEDED)** — budget guard berbasis USD dihapus
  seluruhnya (tidak ada lagi LLM_MONTHLY_BUDGET_USD / LLM_DAILY_BUDGET_USD).
- Konteks: Ekstraksi terstruktur butuh LLM, tapi semua harus Rp0. Proyek
  Google Cloud BuruPromo TIDAK BOLEH punya billing account — tanpa billing,
  API yang melebihi free tier hanya mengembalikan 429, bukan menagih.
- Keputusan:
  1. Gemini API FREE TIER saja via Google AI Studio, tanpa billing account.
  2. Model TIDAK dikunci di dokumen/kode — owner memilih model free tier
     dengan RPD terbesar yang tampil di AI Studio proyeknya, disimpan di
     `.env` (LLM_MODEL). Limit dibaca dari `services/ingest/pipeline/llm_config.py`
     (.env: LLM_MODEL, LLM_RPM, LLM_DAILY_REQUEST_LIMIT, LLM_TPM).
     Default bila .env kosong adalah fallback terburuk (10 RPM / 20 RPD /
     250rb TPM) — bukan janji Google.
  3. Quota guard berbasis JUMLAH REQUEST (`pipeline/llm.py` QuotaGuard):
     kena 429 (RPD habis) -> job berhenti, sisa masuk `llm_queue` (Redis),
     diproses ulang setelah reset tengah malam PT. RPM 429 -> backoff 2/4/8 dtk.
  4. Ekstraksi berbasis aturan dulu (regex tanggal/nilai/kode), cache per
     content_hash; LLM hanya untuk field yang tidak bisa diparse aturan.
  5. TIDAK ADA fallback berbayar (GPT-4o-mini dihapus). Pengganti harus free
     tier lain yang disetujui owner dulu.
- Konsekuensi: dengan RPD 20/hari, maksimal 20 promo/hari lewat LLM — sebagian
  besar promo harus lolos lewat aturan + review manual. Target Fase 1
  (≥200 promo aktif) bisa melambat bila kuota jadi bottleneck; laporkan jujur.
- X API: budget $0, disabled sampai Fase 2.
