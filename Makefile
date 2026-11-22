# BuruPromo — Fase 0 (lokal, Docker Compose). Tanpa deploy berbayar.
.PHONY: dev build lint typecheck test test-py check-fixtures seed meilisearch-settings up down

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

up: ## Nyalakan semua layanan lokal
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down
