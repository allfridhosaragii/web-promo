# BuruPromo

Search engine khusus promo Indonesia — dimulai dari Jawa Timur (fokus Surabaya).
Satu tempat untuk mencari semua promo yang masih berlaku.

> **Status: Fase 0 — skeleton monorepo (Revisi 2: SEMUA GRATIS Rp0).**
> Belum ada konektor produksi yang aktif, belum ada fetch promo live.
> Setelah Fase 0: **vertical slice BCA dulu** (1 konektor end-to-end), baru tambah sumber lain.
> Keputusan owner 2026-11-22 (revisi 2): SEMUA Rp0 kecuali domain.
> LLM = Gemini FREE TIER saja via Google AI Studio, TANPA billing account —
> model dipilih owner dari AI Studio (lihat `.env.example`), quota guard
> berbasis jumlah request (bukan rupiah). Budget berbasis USD DIHAPUS.
> Produksi: Oracle Cloud Always Free (VM ARM A1, 2 OCPU/12 GB) + Caddy.
> X API budget $0, disabled sampai Fase 2.

Dokumen arsitektur: `docs/ARCHITECTURE.md` (Revisi 2)
Katalog sumber terverifikasi: `docs/SOURCES.md` (Revisi 1, 2026-11-22)

## Struktur

```
burupromo/
├─ apps/web/            Next.js App Router + TypeScript strict + design token §9
├─ apps/api/            Hono + Zod, kontrak /v1 (apps/api/openapi.yaml)
├─ services/ingest/     Python 3.12+, BaseConnector (§5.1), quota guard LLM (§11.1),
│                        sinkron Spreadsheet (§17), revalidate via HTTP (§17.4)
├─ packages/contracts/  Zod bersama (PromoSummary / PromoDetail)
├─ packages/db/         Drizzle schema + migrasi + seed wilayah Jatim (38 kab/kota)
├─ packages/ui/         Design tokens + komponen dasar
├─ packages/config/     tsconfig, tailwind preset, biome
├─ infra/               docker-compose (+ .prod.yml), Caddy, backup, Meilisearch settings (§5.2)
└─ docs/                ARCHITECTURE.md, SOURCES.md, ADR
```

## Biaya — semua Rp0 (kecuali domain)

| Komponen | Batas free tier | Kalau habis |
|---|---|---|
| LLM Gemini free tier | Lihat AI Studio proyek owner; fallback terburuk 10 RPM / 20 RPD | Job berhenti (429), antre `llm_queue`, proses ulang setelah reset tengah malam PT |
| Oracle Always Free | 2 OCPU / 12 GB terus-menerus; 200 GB block; 20 GB Object Storage | Jangan buat resource di luar jatah — alert, bukan upgrade |
| Sentry Developer | 5.000 error/bulan, 1 user, retensi 30 hari | Event di-drop, tidak ditagih |
| Umami self-host | Hanya resource VM | — |
| Google Sheets API | 60 tulis/menit/user (service account = 1 user) | Retry backoff, antre `sheets_queue` |
| Backup rclone → Drive | 15 GB Google Drive gratis | Retensi 7 harian + 4 mingguan |

Produksi: `make up-prod` (compose utama + `infra/docker-compose.prod.yml` —
hanya Caddy 80/443 yang terbuka; firewall Oracle hanya 22/80/443).
Backup: lihat `infra/backup/README.md` (cron 02:00 WIB, restore wajib diuji sekali).

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
