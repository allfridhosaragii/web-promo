"""Bangun dokumen Meilisearch dari satu promo (ARCH §5.2, v2).

- `starts_at` / `ends_at` (ISO string) HANYA untuk tampilan.
  Filter & sort memakai `starts_at_ts` / `ends_at_ts` (Unix detik, integer).
- `status` (kolom tunggal lama) DIHAPUS di v2 — diganti dua kolom:
  `lifecycle` (dijadwalkan|aktif|segera_berakhir|kedaluwarsa) dan
  `moderation` (belum_ditinjau|terverifikasi|dilaporkan|ditolak).
- Index utama HANYA: lifecycle IN (aktif, segera_berakhir)
  AND moderation != ditolak AND is_seed = false.
"""

from __future__ import annotations

from datetime import UTC, datetime

INDEXABLE_LIFECYCLES = ("aktif", "segera_berakhir")


def to_unix_ts(value: datetime | str | None) -> int | None:
    """Datetime/ISO -> Unix detik (integer). None bila tidak ada / tidak bisa diparse."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)  # py3.11+ sudah memahami akhiran "Z"
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


def should_index(promo: dict) -> bool:
    """Aturan index utama (ARCH §5.2): lifecycle aktif/segera_berakhir,
    moderation bukan ditolak, bukan seed dev."""
    if promo.get("is_seed"):
        return False
    if promo.get("lifecycle") not in INDEXABLE_LIFECYCLES:
        return False
    return promo.get("moderation") != "ditolak"


def to_meilisearch_doc(promo: dict) -> dict:
    """Satu promo (dict dari Postgres) -> dokumen index `promos`."""
    starts_at = promo.get("starts_at")
    ends_at = promo.get("ends_at")
    return {
        "id": str(promo.get("id", "")),
        "title": promo.get("title", ""),
        "summary": promo.get("summary", ""),
        "brand_name": promo.get("brand_name", ""),
        "brand_slug": promo.get("brand_slug", ""),
        "platform": promo.get("platform", ""),
        "promo_type": promo.get("promo_type"),
        "value_percent": promo.get("value_percent"),
        "value_amount": promo.get("value_amount"),
        "max_discount": promo.get("max_discount"),
        "min_purchase": promo.get("min_purchase"),
        "voucher_code": promo.get("voucher_code"),
        "has_voucher_code": bool(promo.get("voucher_code")),
        "category_ids": promo.get("category_ids") or [],
        "category_slugs": promo.get("category_slugs") or [],
        "category_names": promo.get("category_names") or [],
        "region_scope": promo.get("region_scope"),
        "region_codes": promo.get("region_codes") or [],
        "cluster": promo.get("cluster"),
        "channel": promo.get("channel"),
        "payment_methods": promo.get("payment_methods") or [],
        "requirements": promo.get("requirements") or [],
        "is_student_only": bool(promo.get("is_student_only", False)),
        "starts_at": starts_at.isoformat() if isinstance(starts_at, datetime) else starts_at,
        "ends_at": ends_at.isoformat() if isinstance(ends_at, datetime) else ends_at,
        "starts_at_ts": to_unix_ts(starts_at),
        "ends_at_ts": to_unix_ts(ends_at),
        "lifecycle": promo.get("lifecycle"),
        "moderation": promo.get("moderation"),
        "confidence": promo.get("confidence"),
        "votes_valid": promo.get("votes_valid", 0),
        "saves": promo.get("saves", 0),
        "views": promo.get("views", 0),
        "source_url": promo.get("source_url"),
        "created_at": promo.get("created_at").isoformat()
        if isinstance(promo.get("created_at"), datetime)
        else promo.get("created_at"),
        "is_seed": bool(promo.get("is_seed", False)),
    }
