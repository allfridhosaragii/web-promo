"""Normalisasi teks promo: buang whitespace berlebih, strip tracking dari URL."""

from __future__ import annotations

import re

from connectors.base import canonical_url

_WS = re.compile(r"\s+")


def clean_text(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def normalize_source_url(url: str) -> str:
    return canonical_url(url)
