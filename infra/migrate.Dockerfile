# Migrate one-shot (Drizzle migrasi via packages/db/src/migrate.ts).
# Dijalankan sebagai service `migrate` di docker-compose.yml — depends_on
# postgres healthy, dan api depends_on migrate completed. JANGAN jalankan
# migrasi lewat initdb.d (Postgres hanya mengeksekusi file di root initdb.d,
# bukan subfolder — mount lama sudah dihapus).
#
# Install: pnpm install --frozen-lockfile MURNI (tanpa fallback `|| pnpm install`).
# CMD memakai tsx (one-shot job, bukan server jangka panjang) — itu disengaja.
FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
RUN pnpm install --filter @burupromo/db... --frozen-lockfile
WORKDIR /app/packages/db
CMD ["pnpm", "migrate"]
