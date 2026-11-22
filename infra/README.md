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
- `api.Dockerfile` / `web.Dockerfile` / `ingest.Dockerfile` / `migrate.Dockerfile` —
  image Fase 0. Semua `linux/arm64` (Oracle A1) — CI menjalankan
  `docker buildx build --platform linux/arm64`.
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
