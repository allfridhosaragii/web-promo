"""Geotagging berbasis aturan untuk wilayah Jawa Timur (ARCH §8) + default nasional."""

from __future__ import annotations

_CITY_TO_CODE: dict[str, str] = {
    "surabaya": "35.78",
    "sidoarjo": "35.15",
    "gresik": "35.25",
    "kota malang": "35.73",
    "malang": "35.73",
    "batu": "35.79",
    "mojokerto": "35.76",
    "lamongan": "35.24",
    "bangkalan": "35.26",
    "jember": "35.09",
    "banyuwangi": "35.10",
    "kediri": "35.71",
    "madiun": "35.77",
    "pasuruan": "35.75",
    "probolinggo": "35.74",
    "blitar": "35.72",
}


def geotag_promo(text: str, title: str | None = None) -> tuple[str, list[str]]:
    """Kembalikan (region_scope, region_codes). Default ('nasional', [])."""
    haystack = f"{title or ''} {text}".lower()
    codes: list[str] = []
    for city, code in _CITY_TO_CODE.items():
        if city in haystack and code not in codes:
            codes.append(code)
    if codes:
        return "kota", codes
    if "jawa timur" in haystack or "jatim" in haystack:
        return "provinsi", ["35"]
    return "nasional", []
