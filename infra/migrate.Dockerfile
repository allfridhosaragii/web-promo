# Fase 0: image migrate one-shot (Drizzle migrasi via packages/db/src/migrate.ts).
# Dijalankan sebagai service `migrate` di docker-compose.yml — depends_on
# postgres healthy, dan api depends_on migrate completed. JANGAN jalankan
# migrasi lewat initdb.d (Postgres hanya mengeksekusi file di root initdb.d,
# bukan subfolder — mount lama sudah dihapus).
FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
RUN pnpm install --filter @burupromo/db... --frozen-lockfile || pnpm install --filter @burupromo/db...
WORKDIR /app/packages/db
CMD ["pnpm", "migrate"]
