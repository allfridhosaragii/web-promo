"""Runner sekali jalan untuk Vertical Slice BCA (ARCH §5, §17).

Jalankan dari services/ingest:
    uv run python -m jobs.run_once
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.bank_bca import BankBCAConnector
from connectors.base import RawItem
from pipeline.categorize import categorize_promo
from pipeline.dedup import make_dedup_key
from pipeline.expire import compute_lifecycle
from pipeline.geotag import geotag_promo
from pipeline.index import should_index
from pipeline.llm import LLMExtractor
from pipeline.normalize import clean_text
from pipeline.revalidate import trigger_revalidate
from pipeline.rules import extract_rules, needs_llm
from pipeline.score import score_confidence
from pipeline.store import (
    index_meilisearch,
    is_source_enabled,
    update_source_health,
    upsert_promo,
    upsert_raw_item,
)
from sync.sheets import SheetsSync, build_sheets_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("burupromo.run_once")

_PROMO_KEYWORDS = (
    "promo",
    "diskon",
    "cashback",
    "cicilan",
    "gratis",
    "voucher",
    "spesial",
    "hemat",
    "potongan",
    "reward",
    "poin",
    "berlaku",
)
_BCA_PAYMENTS = (
    "myBCA",
    "BCA mobile",
    "QRIS",
    "Sakuku",
    "Kartu Kredit BCA",
    "Kartu Debit BCA",
    "Paylater BCA",
)


def is_promo_text(text: str, title: str | None = None) -> bool:
    haystack = f"{title or ''} {text}".lower()
    return len(text) >= 20 and any(kw in haystack for kw in _PROMO_KEYWORDS)


def _extract_payments(text: str) -> list[str]:
    low = text.lower()
    found = [p for p in _BCA_PAYMENTS if p.lower() in low]
    return found or ["BCA"]


def _detect_channel(text: str) -> str:
    low = text.lower()
    has_on = "online" in low or ".com" in low or ".co.id" in low or "e-commerce" in low
    has_off = "offline" in low or "outlet" in low or "store" in low or "dine-in" in low
    if has_on and has_off:
        return "keduanya"
    if has_off:
        return "offline"
    return "online"


def _build_summary(text: str, title: str) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= 240:
        return cleaned
    return cleaned[:237].rstrip() + "..."


def _run_sheets_sync(promos: list[dict]) -> str:
    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "").strip()
    if not spreadsheet_id or not sa_path or not Path(sa_path).exists():
        logger.info("Sheets tidak dikonfigurasi, sinkron dilewati.")
        return "dilewati (tidak dikonfigurasi)"
    client = build_sheets_client(spreadsheet_id, sa_path)
    sync = SheetsSync(client)
    for p in promos:
        sync.enqueue(p)
    res = sync.flush()
    return f"sukses ({res})"


async def run_bca_once(limit: int = 20) -> dict:
    if not is_source_enabled("bca"):
        logger.warning("Sumber 'bca' sedang disabled (kill switch). Run dibatalkan.")
        return {"skipped": True, "reason": "source_disabled"}

    connector = BankBCAConnector()
    health = await connector.health_check()
    update_source_health(health)
    logger.info(
        "Health check BCA: ok=%s items_found=%s latency_ms=%s error=%s",
        health.ok,
        health.items_found,
        health.latency_ms,
        health.last_error,
    )
    if not health.ok:
        return {"skipped": True, "reason": f"health_check_failed: {health.last_error}"}

    raw_items: list[RawItem] = await connector.fetch(limit=limit)
    llm = LLMExtractor()
    now = datetime.now(UTC)

    classified_ok = 0
    upserted: list[dict] = []
    failed: list[str] = []

    for raw in raw_items:
        try:
            item = connector.parse(raw)
            upsert_raw_item(item)
            if not is_promo_text(item.text, item.title):
                continue
            classified_ok += 1

            partial = extract_rules(item.text, now=now)
            if needs_llm(partial):
                llm_res = await llm.extract(item.text, content_hash=item.content_hash)
                if llm_res.llm_used:
                    for k, v in llm_res.fields.items():
                        if k not in partial and v is not None:
                            partial[k] = v

            title = item.title or item.text[:80]
            promo_type = partial.get("promo_type") or "lainnya"
            starts_at = partial.get("starts_at") or now
            ends_at = partial.get("ends_at")
            lifecycle = compute_lifecycle(starts_at, ends_at, now=now, last_confirmed_at=now)
            region_scope, region_codes = geotag_promo(item.text, title)
            category_slugs = categorize_promo(item.text, title)
            dedup_key = make_dedup_key(connector.source_id, item.source_url)
            confidence = score_confidence(
                source_type=connector.source_type,
                has_dates=ends_at is not None,
                has_voucher_code=bool(partial.get("voucher_code")),
            )

            promo_record = {
                "title": title,
                "summary": _build_summary(item.text, title),
                "promo_type": promo_type,
                "value_percent": partial.get("value_percent"),
                "value_amount": partial.get("value_amount"),
                "max_discount": partial.get("max_discount"),
                "min_purchase": partial.get("min_purchase"),
                "voucher_code": partial.get("voucher_code"),
                "how_to_claim": None,
                "payment_methods": _extract_payments(item.text),
                "requirements": [],
                "channel": _detect_channel(item.text),
                "platform": "BCA",
                "category_slugs": category_slugs,
                "brand_slug": "bca",
                "region_scope": region_scope,
                "region_codes": region_codes,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "recurring_rule": partial.get("recurring_rule"),
                "quota_note": None,
                "source_id": connector.source_id,
                "source_url": item.source_url,
                "evidence_image_url": None,
                "confidence": confidence,
                "lifecycle": lifecycle,
                "moderation": "belum_ditinjau",
                "dedup_key": dedup_key,
            }
            saved = upsert_promo(promo_record)
            upserted.append(saved)
        except Exception as exc:
            logger.exception("Gagal proses item %s", raw.source_url)
            failed.append(f"{raw.source_url}: {exc}")

    indexed = index_meilisearch(upserted)
    sheets_status = _run_sheets_sync(upserted)
    revalidated = trigger_revalidate()

    indexable_count = sum(1 for p in upserted if should_index(p))
    summary = {
        "raw_items": len(raw_items),
        "classified_ok": classified_ok,
        "upserted_postgres": len(upserted),
        "indexable": indexable_count,
        "indexed_meilisearch": indexed,
        "sheets_sync": sheets_status,
        "web_revalidated": revalidated,
        "failed": failed,
    }
    print("=== RINGKASAN RUN BCA ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary


if __name__ == "__main__":
    asyncio.run(run_bca_once())
