# BuruPromo

Search engine khusus promo Indonesia — dimulai dari Jawa Timur (fokus Surabaya).
Satu tempat untuk mencari semua promo yang masih berlaku.

> **Status: Fase 0 — skeleton monorepo.** Belum ada konektor produksi yang aktif,
> belum ada fetch promo live, belum ada deploy berbayar.
> Setelah Fase 0: **vertical slice BCA dulu** (1 konektor end-to-end), baru tambah sumber lain.
> Keputusan owner 2026-11-22: LLM Gemini 2.5 Flash-Lite, maks $5/bulan, budget guard wajib.
> Deploy lokal (Docker Compose) dulu. X API budget $0, disabled sampai Fase 2.

Dokumen arsitektur: `docs/ARCHITECTURE.md` (Revisi 1)
Katalog sumber terverifikasi: `docs/SOURCES.md` (Revisi 1, 2026-11-22)

## Struktur

```
burupromo/
├─ apps/web/            Next.js App Router + TypeScript strict + design token §9
├─ apps/api/            Hono + Zod, kontrak /v1 (apps/api/openapi.yaml)
├─ services/ingest/     Python 3.12+, BaseConnector (§5.1), budget guard LLM
├─ packages/contracts/  Zod bersama (PromoSummary / PromoDetail)
├─ packages/db/         Drizzle schema + migrasi + seed wilayah Jatim (38 kab/kota)
├─ packages/ui/         Design tokens + komponen dasar
├─ packages/config/     tsconfig, tailwind preset, biome
├─ infra/               docker-compose, Meilisearch settings (§5.2)
└─ docs/                ARCHITECTURE.md, SOURCES.md, ADR
```

## Cara menjalankan (lokal)

```bash
cp .env.example .env        # isi seperlunya; GEMINI_API_KEY kosong = tidak ada panggilan berbayar
pnpm install                # butuh Node 20+ dan pnpm 9
docker compose -f infra/docker-compose.yml up -d   # postgres, redis, meilisearch, api, web, ingest
pnpm seed                   # seed wilayah Jawa Timur — gagal kalau bukan 38 kab/kota
bash infra/meilisearch/apply-settings.sh
pnpm dev                    # web http://localhost:3000, api http://localhost:3001
```

Perintah lain: `make lint`, `make typecheck`, `make test`, `make check-fixtures`.

## Aturan keras

- Utamakan API resmi & feed afiliasi. Scraping hanya halaman publik tanpa login,
  hormati `robots.txt`, ≤1 req/detik/domain, User-Agent jujur.
- **Dilarang:** bypass login/captcha, akun palsu, cookie curian, salin konten utuh.
- **Dilarang** memakai `/api/` internal AZKO / Klik Indomaret yang di-Disallow,
  dan dilarang crawl sumber yang ditandai `disabled` di SOURCES.md (Alfamart, Alfamidi).
- Data dummy hanya `is_seed=true` dan **tidak masuk index produksi**.
- Fixture test **wajib** untuk setiap konektor sejak Fase 1 (`make check-fixtures`).
- Semua waktu disimpan UTC, ditampilkan WIB. `segera_berakhir` = `ends_at` < 24 jam.
  TTL `raw_items` 30 hari.
