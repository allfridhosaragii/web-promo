# infra

- `docker-compose.yml` — postgres 16 (PostGIS + pgvector via `postgres/Dockerfile`),
  Redis/Valkey, Meilisearch, `migrate` (one-shot), api, web, ingest, Caddy,
  Umami. Jalankan dari root: `make up`.
  **Belum terverifikasi dengan `docker compose up`** — Docker tidak ada di VM ini.
  Verifikasi `docker compose config` dan build image adalah langkah pertama
  saat ada mesin dengan Docker.
- `docker-compose.prod.yml` — override PRODUKSI (D8): `!reset` semua `ports`
  internal (Postgres/Redis/Meilisearch/API/Web/Umami) — hanya Caddy 80/443
  yang terbuka. Dipakai: `make up-prod` (butuh Compose >= 2.24 + DOMAIN diisi).
- `migrate.Dockerfile` + service `migrate` — migrasi Drizzle one-shot
  (`packages/db/src/migrate.ts`, menjalankan `migrations/*.sql` berurutan).
  JANGAN mount migrasi ke initdb.d — Postgres hanya mengeksekusi file di ROOT
  initdb.d, bukan subfolder (D9). `api` menunggu `migrate` selesai
  (`service_completed_successfully`) sebelum start.
- `caddy/Caddyfile` — reverse proxy + HTTPS otomatis (Let's Encrypt, gratis).
  `/api/*` dan `/v1/*` → api:3001, `/umami/*` → umami:3000, sisanya → web:3000.
  DOMAIN dari env `DOMAIN` (kosong = http://localhost, dev).
- `meilisearch/settings.json` — skema index `promos` persis ARCHITECTURE.md §5.2
  (v2: `starts_at_ts`/`ends_at_ts` Unix detik, `lifecycle` + `moderation`,
  sinonim dua arah). Terapkan: `bash infra/meilisearch/apply-settings.sh`
  (jangan ubah via dashboard tanpa commit).
- `postgres/Dockerfile` + `init/01-extensions.sql` + `init/02-umami-schema.sql` —
  postgis, vector, pgcrypto; schema `umami` terpisah untuk analitik.
  **Postgres TIDAK memakai `postgis/postgis`** — image itu amd64 tunggal
  (terverifikasi via registry: manifest tunggal `amd64/linux`), jadi tidak
  bisa jalan di VM ARM Ampere A1. Sebagai gantinya `FROM postgres:16`
  (multi-arch) + `apt install postgresql-16-postgis-3 postgresql-16-pgvector`
  dari repo PGDG yang sudah ada di image resmi `postgres:16`.
- `api.Dockerfile` / `web.Dockerfile` / `ingest.Dockerfile` / `migrate.Dockerfile` —
  image Fase 0. Semua `linux/arm64` (Oracle A1) — CI menjalankan
  `docker buildx build --platform linux/arm64`.

## ARM64 — status image (terverifikasi 2026-11-22 via manifest registry)

Dicek langsung ke Docker Hub / GHCR registry API (bukan klaim dari halaman
marketing). Semua image di bawah ini punya `arm64/linux` di manifest-nya:

| Image | Arsitektur di manifest |
|---|---|
| `postgres:16` | 386, amd64, arm, **arm64**, ppc64le, riscv64, s390x |
| `valkey/valkey:8-alpine` | amd64, arm, **arm64**, ppc64le |
| `getmeili/meilisearch:v1.12` | amd64, **arm64** |
| `node:22-alpine` | amd64, arm, **arm64**, s390x |
| `python:3.12-slim` | 386, amd64, arm, **arm64**, ppc64le, riscv64, s390x |
| `caddy:2-alpine` | amd64, arm, **arm64**, ppc64le, riscv64, s390x |
| `ghcr.io/umami-software/umami:postgresql-latest` | amd64, **arm64** |
| `postgis/postgis:16-3.4` | **amd64 SAJA (manifest tunggal) — JANGAN dipakai** |

**BELUM terverifikasi:** `docker buildx build --platform linux/arm64` untuk
kelima Dockerfile dan `docker compose up` — Docker TIDAK ada di VM ini.
Job `build-arm64` di CI adalah yang pertama kali membuktikan build ini;
jangan klaim image produksi lolos sebelum job itu hijau.

## Build produksi (bukan `pnpm dev` / `tsx` di server)

- **API** (`api.Dockerfile`): `pnpm install --frozen-lockfile` (murni, tanpa
  fallback `|| pnpm install`) → `pnpm --filter @burupromo/api build`
  (tsup, bundel `src/index.ts` + paket workspace `@burupromo/*` jadi
  `dist/index.js`) → `CMD ["node", "dist/index.js"]`. `tsc` saja TIDAK cukup:
  paket workspace main-nya masih `.ts` dan Node tidak bisa menjalankannya
  (pernah gagal `ERR_MODULE_NOT_FOUND './promo'`). Build ini sudah diuji
  lokal: `dist/index.js` 128 KB, `/health` 200, `/v1/promos` 200.
- **Web** (`web.Dockerfile`): `pnpm install --frozen-lockfile` (murni) →
  `pnpm --filter @burupromo/web build` (`next build`) → `CMD ["pnpm", "start"]`
  (`next start`). Dipakai `next start`, BUKAN output standalone.
- **Migrate** (`migrate.Dockerfile`): `pnpm install --frozen-lockfile` (murni)
  → `CMD ["pnpm", "migrate"]` (tsx, one-shot job — bukan server, jadi tsx
  di sini disengaja).
- **Ingest** (`ingest.Dockerfile`): `uv sync --frozen` MURNI (tanpa fallback
  `|| uv sync`). `uv.lock` WAJIB ada dan cocok dengan `pyproject.toml`.
- **Postgres** (`postgres/Dockerfile`): lihat catatan `postgis/postgis` di atas.
- `backup/` — `backup.sh` (pg_dump → gzip → rclone ke Google Drive) +
  `crontab.example` (02:00 WIB) + README (uji restore wajib sekali di Fase 0).

## Firewall produksi (Oracle — cek manual di console, D8)

Security list / NSG VM **HANYA** membuka:

| Port | Untuk | Sumber |
|---|---|---|
| 22 | SSH | IP owner saja (jangan 0.0.0.0/0) |
| 80 | HTTP (Caddy → redirect HTTPS) | 0.0.0.0/0 |
| 443 | HTTPS (Caddy + Let's Encrypt) | 0.0.0.0/0 |

JANGAN buka 5432 (Postgres), 6379 (Redis), 7700 (Meilisearch), 3000 (web),
3001 (api), 3002 (Umami) ke publik — semua itu hanya lewat jaringan internal
Compose atau via Caddy. `docker-compose.prod.yml` sudah menghapus publish
port-nya; firewall adalah lapis kedua.
