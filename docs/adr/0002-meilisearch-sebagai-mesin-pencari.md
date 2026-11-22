# ADR 0002 — Meilisearch sebagai mesin pencari

- Status: Diterima (Fase 0, 2026-11-22)
- Konteks: Pencarian promo butuh typo tolerance, sinonim Bahasa Indonesia,
  faceting, dan sort — tanpa membangun search sendiri di Postgres.
- Keputusan: Meilisearch (index `promos`, `promos_dev` untuk dev).
  Postgres sumber kebenaran data, Meilisearch sumber kebenaran pencarian.
  Settings di `infra/meilisearch/settings.json` (ARCHITECTURE.md §5.2).
  `is_seed=true` tidak pernah masuk index produksi; `kedaluwarsa`/`ditolak`/
  `dilaporkan` keluar dari index utama.
- Alternatif yang ditolak sementara: Typesense (dipakai bila skala besar).
