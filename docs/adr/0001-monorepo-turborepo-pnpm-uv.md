# ADR 0001 — Monorepo Turborepo + pnpm (TS) + uv (Python)

- Status: Diterima (Fase 0, 2026-11-22)
- Konteks: BuruPromo punya tiga dunia — web/API TypeScript dan ingestion Python
  (scraping/OCR/NLP paling matang di Python). Satu repo, dua toolchain.
- Keputusan: Turborepo + pnpm untuk bagian TypeScript, uv untuk Python.
  Docker Compose untuk layanan lokal. Deploy lokal dulu, tanpa deploy berbayar.
- Konsekuensi: dua lockfile (pnpm-lock.yaml + uv.lock), CI dua job (ts + python).
