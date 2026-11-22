# Web produksi (Next.js) — `next build` + `next start`, BUKAN `pnpm dev`.
#
# Install: pnpm install --frozen-lockfile MURNI (tanpa fallback `|| pnpm install`).
# Kalau lockfile tidak cocok, build GAGAL dengan jelas.
# Dipakai `next start` (bukan output standalone) — lihat infra/README.md.
FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
COPY apps/web ./apps/web
RUN pnpm install --filter @burupromo/web... --frozen-lockfile
RUN pnpm --filter @burupromo/web build
WORKDIR /app/apps/web
CMD ["pnpm", "start"]
