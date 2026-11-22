# Postgres 16 + PostGIS + pgvector. postgis/postgis tidak membawa pgvector,
# jadi install dari apt (postgresql-16-pgvector) saat build image.
FROM postgis/postgis:16-3.4
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-16-pgvector \
  && rm -rf /var/lib/apt/lists/*
COPY init/01-extensions.sql /docker-entrypoint-initdb.d/01-extensions.sql
