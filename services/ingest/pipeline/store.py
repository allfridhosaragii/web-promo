"""Penyimpanan hasil pipeline ke Postgres + Meilisearch (ARCH §5, §5.2)."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

import httpx
import psycopg
from psycopg.rows import dict_row

from connectors.base import HealthStatus, RawItem
from pipeline.index import should_index, to_meilisearch_doc

logger = logging.getLogger(__name__)


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL belum diisi")
    return url


def is_source_enabled(source_id: str) -> bool:
    """Cek kill switch di tabel sources."""
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT enabled FROM sources WHERE source_id = %s", (source_id,)
        ).fetchone()
    return bool(row and row["enabled"])


def update_source_health(health: HealthStatus) -> None:
    with psycopg.connect(_db_url()) as conn:
        conn.execute(
            """
            UPDATE sources
            SET last_success_at = COALESCE(%s, last_success_at),
                last_error = %s,
                last_latency_ms = %s
            WHERE source_id = %s
            """,
            (
                health.last_success_at if health.ok else None,
                None if health.ok else health.last_error,
                health.latency_ms,
                health.source_id,
            ),
        )
        conn.commit()


def upsert_raw_item(item: RawItem) -> None:
    with psycopg.connect(_db_url()) as conn:
        conn.execute(
            """
            INSERT INTO raw_items (source_id, source_url, title, text, html, media_urls, content_hash, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (content_hash) DO UPDATE
            SET fetched_at = EXCLUDED.fetched_at,
                title = COALESCE(EXCLUDED.title, raw_items.title)
            """,
            (
                item.source_id,
                item.source_url,
                item.title,
                item.text,
                item.html,
                json.dumps(item.media_urls),
                item.content_hash,
                item.fetched_at or datetime.now(UTC),
            ),
        )
        conn.commit()


def upsert_promo(promo: dict) -> dict:
    """Upsert promo ke Postgres berdasarkan dedup_key, kembalikan record lengkap untuk Meilisearch/Sheets."""
    now = datetime.now(UTC)
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        brand = conn.execute(
            "SELECT id, name, slug FROM brands WHERE slug = %s",
            (promo["brand_slug"],),
        ).fetchone()
        brand_id = brand["id"] if brand else None

        cat_rows = conn.execute(
            "SELECT id, slug, name FROM categories WHERE slug = ANY(%s)",
            (promo.get("category_slugs") or [],),
        ).fetchall()
        category_ids = [str(r["id"]) for r in cat_rows]
        category_names = [r["name"] for r in cat_rows]

        row = conn.execute(
            """
            INSERT INTO promos (
                title, summary, promo_type, value_percent, value_amount,
                max_discount, min_purchase, voucher_code, how_to_claim,
                payment_methods, requirements, channel, platform,
                category_ids, brand_id, region_scope, region_codes,
                starts_at, ends_at, recurring_rule, quota_note,
                source_id, source_url, evidence_image_url,
                confidence, lifecycle, moderation,
                last_checked_at, last_confirmed_at, dedup_key, is_seed, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s, %s,
                %s::jsonb, %s, %s, %s::jsonb,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, FALSE, %s
            )
            ON CONFLICT (dedup_key) DO UPDATE SET
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                promo_type = EXCLUDED.promo_type,
                value_percent = EXCLUDED.value_percent,
                value_amount = EXCLUDED.value_amount,
                max_discount = EXCLUDED.max_discount,
                min_purchase = EXCLUDED.min_purchase,
                voucher_code = EXCLUDED.voucher_code,
                payment_methods = EXCLUDED.payment_methods,
                requirements = EXCLUDED.requirements,
                channel = EXCLUDED.channel,
                category_ids = EXCLUDED.category_ids,
                region_scope = EXCLUDED.region_scope,
                region_codes = EXCLUDED.region_codes,
                starts_at = EXCLUDED.starts_at,
                ends_at = EXCLUDED.ends_at,
                confidence = EXCLUDED.confidence,
                lifecycle = EXCLUDED.lifecycle,
                last_checked_at = EXCLUDED.last_checked_at,
                last_confirmed_at = EXCLUDED.last_confirmed_at,
                updated_at = EXCLUDED.updated_at
            RETURNING id, created_at
            """,
            (
                promo["title"],
                promo["summary"],
                promo["promo_type"],
                promo.get("value_percent"),
                promo.get("value_amount"),
                promo.get("max_discount"),
                promo.get("min_purchase"),
                promo.get("voucher_code"),
                promo.get("how_to_claim"),
                json.dumps(promo.get("payment_methods") or []),
                json.dumps(promo.get("requirements") or []),
                promo.get("channel", "keduanya"),
                promo.get("platform", "BCA"),
                json.dumps(category_ids),
                brand_id,
                promo.get("region_scope", "nasional"),
                json.dumps(promo.get("region_codes") or []),
                promo.get("starts_at") or now,
                promo.get("ends_at"),
                promo.get("recurring_rule"),
                promo.get("quota_note"),
                promo["source_id"],
                promo["source_url"],
                promo.get("evidence_image_url"),
                promo["confidence"],
                promo["lifecycle"],
                promo.get("moderation", "belum_ditinjau"),
                now,
                now,
                promo["dedup_key"],
                now,
            ),
        ).fetchone()

        promo_id = str(row["id"])
        conn.execute(
            """
            INSERT INTO promo_sources (promo_id, source_id, source_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (promo_id, source_id) DO NOTHING
            """,
            (promo_id, promo["source_id"], promo["source_url"]),
        )
        conn.commit()

    return {
        **promo,
        "id": promo_id,
        "brand_name": brand["name"] if brand else promo.get("brand_name", "BCA"),
        "brand_slug": brand["slug"] if brand else promo["brand_slug"],
        "category_ids": category_ids,
        "category_names": category_names,
        "created_at": row["created_at"],
        "last_checked_at": now,
        "is_seed": False,
    }


def index_meilisearch(promos: list[dict]) -> int:
    """Index promo ke Meilisearch (hanya yang lolos should_index). Kembalikan jumlah terindeks."""
    host = os.environ.get("MEILISEARCH_HOST", "").rstrip("/")
    key = os.environ.get("MEILISEARCH_MASTER_KEY", "")
    index_name = os.environ.get("MEILISEARCH_INDEX_PROMOS", "promos")
    if not host:
        logger.warning("MEILISEARCH_HOST kosong, skip indexing")
        return 0

    docs = [to_meilisearch_doc(p) for p in promos if should_index(p)]
    if not docs:
        return 0
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = httpx.post(
            f"{host}/indexes/{index_name}/documents?primaryKey=id",
            json=docs,
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        task_uid = resp.json().get("taskUid")
        if task_uid is not None:
            import time

            for _ in range(25):
                t_resp = httpx.get(f"{host}/tasks/{task_uid}", headers=headers, timeout=10.0)
                t_resp.raise_for_status()
                t_data = t_resp.json()
                status = t_data.get("status")
                if status == "succeeded":
                    return int(t_data.get("details", {}).get("indexedDocuments", len(docs)))
                if status in ("failed", "canceled"):
                    logger.warning("Meilisearch task %s gagal: %s", task_uid, t_data.get("error"))
                    return 0
                time.sleep(0.2)
        return len(docs)
    except httpx.HTTPError as exc:
        logger.warning("Meilisearch tidak terjangkau (%s), skip indexing", exc)
        return 0
