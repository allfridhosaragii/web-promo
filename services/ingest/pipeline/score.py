"""Skor confidence — sumber resmi > akun brand > afiliasi > komunitas.
Ada tanggal jelas? Ada kode? Diverifikasi voting? (ARCHITECTURE.md §5)."""

from __future__ import annotations

BASE = {"official_api": 0.85, "public_web": 0.75, "affiliate_feed": 0.65, "community": 0.45}


def score_confidence(
    *,
    source_type: str,
    has_dates: bool,
    has_voucher_code: bool,
    votes_valid: int = 0,
    votes_invalid: int = 0,
) -> float:
    score = BASE.get(source_type, 0.5)
    if has_dates:
        score += 0.1
    if has_voucher_code:
        score += 0.05
    if votes_valid > 0:
        score += min(0.05, votes_valid * 0.01)
    if votes_invalid > 0:
        score -= min(0.2, votes_invalid * 0.05)
    return round(max(0.0, min(1.0, score)), 2)
