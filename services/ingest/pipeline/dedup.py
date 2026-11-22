"""Pembuatan dedup_key deterministik untuk mencegah duplikat promo di Postgres."""

from __future__ import annotations

import hashlib


def make_dedup_key(source_id: str, source_url: str) -> str:
    """Kunci dedup deterministik per sumber + URL kanonis."""
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
    return f"{source_id}:{digest}"
