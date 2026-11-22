# infra

- `docker-compose.yml` — postgres 16 (PostGIS + pgvector via `postgres/Dockerfile`),
  Redis/Valkey, Meilisearch, api, web, ingest. Jalankan dari root: `make up`.
- `meilisearch/settings.json` — skema index `promos` persis ARCHITECTURE.md §5.2.
  Terapkan: `bash infra/meilisearch/apply-settings.sh` (jangan ubah via dashboard tanpa commit).
- `postgres/Dockerfile` + `init/01-extensions.sql` — postgis, vector, pgcrypto.
- `api.Dockerfile` / `web.Dockerfile` / `ingest.Dockerfile` — image Fase 0.
  **Belum terverifikasi dengan `docker compose up`** — Docker tidak ada di VM ini.
  Verifikasi `docker compose config` dan build image adalah langkah pertama
  saat ada mesin dengan Docker.
