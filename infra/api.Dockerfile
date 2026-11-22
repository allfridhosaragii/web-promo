# API produksi (Hono) — build produksi, BUKAN pnpm dev.
#
# Build: tsup membundel src/index.ts + workspace packages (@burupromo/* yang
# main-nya masih .ts) jadi dist/index.js tunggal. `tsc` saja TIDAK cukup:
# tsconfig api memakai noEmit + moduleResolution bundler, dan Node tidak bisa
# menjalankan .ts workspace secara langsung.
# Install: pnpm install --frozen-lockfile MURNI (tanpa fallback `|| pnpm install`).
# Kalau lockfile tidak cocok, build GAGAL dengan jelas — jangan sembunyikan
# dengan fallback yang menginstal versi tak terkunci.
FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN pnpm install --filter @burupromo/api... --frozen-lockfile
RUN pnpm --filter @burupromo/api build
WORKDIR /app/apps/api
CMD ["node", "dist/index.js"]
