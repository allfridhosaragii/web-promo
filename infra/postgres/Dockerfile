# Postgres 16 + PostGIS + pgvector — ARM64 (Oracle Cloud Always Free, A1).
#
# postgis/postgis TIDAK punya image arm64 (hanya amd64) — Postgres tidak bisa
# jalan di VM ARM Ampere A1 bila memakai image itu. JANGAN pakai postgis/postgis.
#
# Solusi: FROM postgres:16 (image resmi, multi-arch linux/amd64,linux/arm64)
# lalu apt install postgresql-16-postgis-3 + postgresql-16-pgvector dari repo
# PGDG (apt.postgresql.org) yang SUDAH ada di image resmi postgres:16 —
# tanpa repo pihak ketiga tambahan. Ekstensi diaktifkan 01-extensions.sql.
FROM postgres:16
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-postgis-3 \
    postgresql-16-pgvector \
  && rm -rf /var/lib/apt/lists/*
COPY init/01-extensions.sql /docker-entrypoint-initdb.d/01-extensions.sql
