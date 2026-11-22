#!/usr/bin/env bash
# Terapkan infra/meilisearch/settings.json ke index `promos` (dan `promos_dev` bila ada).
# Butuh Meilisearch jalan (docker compose up) + MEILISEARCH_HOST / MEILISEARCH_MASTER_KEY.
set -euo pipefail
HOST="${MEILISEARCH_HOST:-http://localhost:7700}"
KEY="${MEILISEARCH_MASTER_KEY:-}"
INDEX="${MEILISEARCH_INDEX_PROMOS:-promos}"
AUTH=()
[ -n "$KEY" ] && AUTH=(-H "Authorization: Bearer $KEY")
curl -s -X PATCH "$HOST/indexes/$INDEX/settings" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  --data-binary @infra/meilisearch/settings.json
echo "Settings Meilisearch diterapkan ke index $INDEX."
