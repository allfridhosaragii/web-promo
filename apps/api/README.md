# @burupromo/api

Hono + Zod (ARCHITECTURE.md §3.2, §16). Kontrak di `packages/contracts`,
OpenAPI ringkas di `openapi.yaml`.

Fase 0: `GET /v1/promos` mengembalikan list kosong yang jujur (belum ada promo
terindeks), `GET /v1/promos/:id` 404, vote/report 501 (butuh auth, Fase 1).
Rate limit 60 req/menit/IP publik — diterapkan di depan API saat deploy lokal
(lihat infra/docker-compose.yml, nginx — Fase 1).

Jalankan: `pnpm --filter @burupromo/api dev` (port 3001).
