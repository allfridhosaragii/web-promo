# Fase 0: image API (Hono). Build workspace TS — diisi penuh saat vertical slice.
FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN pnpm install --filter @burupromo/api... --frozen-lockfile || pnpm install --filter @burupromo/api...
WORKDIR /app/apps/api
CMD ["pnpm", "dev"]
