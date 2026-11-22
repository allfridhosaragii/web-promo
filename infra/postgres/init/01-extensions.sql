-- Ekstensi Fase 0. Kalau pgvector tidak tersedia, baris vector gagal —
-- itu sinyal, bukan untuk disembunyikan: laporkan dan lanjutkan tanpa embedding.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
