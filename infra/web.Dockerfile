FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json biome.json ./
COPY packages ./packages
COPY apps/web ./apps/web
RUN pnpm install --filter @burupromo/web... --frozen-lockfile || pnpm install --filter @burupromo/web...
WORKDIR /app/apps/web
CMD ["pnpm", "dev"]
