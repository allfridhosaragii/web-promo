# @burupromo/db

Drizzle schema + migrasi + seed wilayah (ARCHITECTURE.md §4, §7).

- `src/schema.ts` — semua tabel (regions, brands, outlets, sources, raw_items,
  promos, categories, users, saved_promos, saved_searches, wallet_preferences,
  submissions, reports, votes, moderation_log, promo_sources).
- `migrations/0001_init.sql` — migrasi awal. `embedding` masih TEXT di Fase 0;
  kolom pgvector `vector(768)` diaktifkan saat pgvector terverifikasi di DB.
- `seed/wilayah/` — snapshot CSV Kepmendagri 300.2.2-2138-2025 + `MANIFEST.md`
  (SHA-256, sumber, kekurangan geometri). `pnpm seed` gagal kalau bukan 38 kab/kota.
- `seed/synonyms.json` — sinonim awal Meilisearch (cermin §5.2).
