"""Expire job — hitung ulang status promo + buat kemunculan berikutnya untuk
promo berulang. Implementasi DB penuh di vertical slice; logika murni ada di
pipeline/expire.py dan sudah dites (pipeline/tests/test_expire.py)."""

from __future__ import annotations

from pipeline.expire import compute_lifecycle, compute_status

__all__ = ["compute_lifecycle", "compute_status"]
