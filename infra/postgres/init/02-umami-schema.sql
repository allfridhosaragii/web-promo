-- 02-umami-schema — Umami self-host pakai Postgres yang sama, schema terpisah.
-- ARCH §3.5.3 (revisi 2): analitik Rp0, data di Postgres yang sama, schema `umami`.
-- Umami dihubungkan dengan DATABASE_URL ...?schema=umami (lihat docker-compose.yml).
CREATE SCHEMA IF NOT EXISTS umami;
