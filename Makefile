# BuruPromo — Fase 0 (lokal, Docker Compose). Revisi 2: SEMUA Rp0.
.PHONY: dev build lint typecheck test test-py check-fixtures seed meilisearch-settings up up-prod down migrate

dev: ## Jalankan web + api (butuh pnpm install dulu)
	pnpm dev

build:
	pnpm build

lint:
	pnpm lint:ts
	cd services/ingest && uv run ruff check . && uv run ruff format --check .

typecheck:
	pnpm typecheck

test:
	pnpm test
	cd services/ingest && uv run pytest -q

test-py:
	cd services/ingest && uv run pytest -q

check-fixtures: ## Gagal kalau ada konektor tanpa fixture
	python3 services/ingest/scripts/check_fixtures.py

seed: ## Seed wilayah Jawa Timur (gagal kalau bukan 38 kab/kota)
	cd packages/db && pnpm seed

meilisearch-settings:
	bash infra/meilisearch/apply-settings.sh

up: ## Nyalakan semua layanan lokal (migrate jalan dulu, one-shot)
	docker compose -f infra/docker-compose.yml up -d

up-prod: ## Nyalakan di VM produksi (hanya Caddy 80/443 terbuka, butuh DOMAIN)
	docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d

migrate: ## Jalankan migrasi Drizzle (one-shot, bukan initdb.d)
	docker compose -f infra/docker-compose.yml run --rm migrate

down:
	docker compose -f infra/docker-compose.yml down
