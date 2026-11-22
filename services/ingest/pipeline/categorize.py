"""Kategorisasi promo berbasis aturan ke taksonomi 12 kategori (ARCH §7)."""

from __future__ import annotations

_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "makanan-minuman",
        (
            "restoran",
            "kuliner",
            "makan",
            "minum",
            "kopi",
            "cafe",
            "kafe",
            "pizza",
            "food",
            "beverage",
            "dine-in",
            "bakmi",
            "sushi",
            "bakery",
            "roti",
        ),
    ),
    (
        "elektronik-gadget",
        (
            "elektronik",
            "gadget",
            "smartphone",
            "laptop",
            "huawei",
            "samsung",
            "apple",
            "mac mini",
            "tv",
            "kamera",
            "appliances",
        ),
    ),
    (
        "kebutuhan-harian",
        (
            "minimarket",
            "supermarket",
            "groceries",
            "grocery",
            "fresh market",
            "indomaret",
            "alfamart",
            "alfamidi",
            "hypermart",
            "superindo",
        ),
    ),
    (
        "fashion",
        ("fashion", "pakaian", "baju", "sepatu", "tas", "batik", "leather", "apparel", "hijab"),
    ),
    (
        "rumah-perabot",
        ("perabot", "furniture", "rumah tangga", "informa", "azko", "ikea", "dekorasi"),
    ),
    (
        "kecantikan-perawatan",
        ("kecantikan", "skincare", "kosmetik", "salon", "spa", "health and beauty", "klinik"),
    ),
    (
        "ecommerce",
        ("e-commerce", "ecommerce", "shopee", "tokopedia", "lazada", "blibli", "online store"),
    ),
    (
        "transportasi-travel",
        ("travel", "tiket", "pesawat", "hotel", "kereta", "ojol", "garuda", "airlines", "trip"),
    ),
    (
        "hiburan",
        (
            "bioskop",
            "cinema",
            "xxi",
            "cgv",
            "streaming",
            "game",
            "konser",
            "event",
            "entertainment",
            "rekreasi",
        ),
    ),
    (
        "pendidikan-mahasiswa",
        ("pendidikan", "kursus", "pelajar", "mahasiswa", "kampus", "universitas"),
    ),
    (
        "pulsa-data-tagihan",
        ("pulsa", "paket data", "telco", "im3", "telkomsel", "xl", "tagihan", "listrik", "pln"),
    ),
    (
        "keuangan",
        (
            "kartu kredit",
            "kartu debit",
            "qris",
            "mybca",
            "bca mobile",
            "sakuku",
            "cicilan",
            "paylater",
            "bank",
        ),
    ),
]


def categorize_promo(text: str, title: str | None = None) -> list[str]:
    """Kembalikan daftar category_slug yang cocok (minimal 1, default 'keuangan' untuk bank)."""
    haystack = f"{title or ''} {text}".lower()
    matched: list[str] = []
    for slug, keywords in _CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            matched.append(slug)
    return matched or ["keuangan"]
