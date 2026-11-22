"""Pydantic schemas — cermin packages/contracts (Zod). Validasi output LLM."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PromoExtract(BaseModel):
    """Hasil ekstraksi LLM terstruktur. Field yang tidak diketahui = None, bukan tebakan."""

    title: str
    summary: str
    promo_type: str = Field(
        pattern=r"^(persen|potongan_nominal|cashback|beli_x_gratis_y|gratis_ongkir|harga_spesial|bundling|poin|cicilan_0|lainnya)$"
    )
    value_percent: float | None = None
    value_amount: int | None = None
    max_discount: int | None = None
    min_purchase: int | None = None
    voucher_code: str | None = None
    how_to_claim: str | None = None
    payment_methods: list[str] = []
    requirements: list[str] = []
    channel: str = Field(default="online", pattern=r"^(online|offline|keduanya)$")
    starts_at: datetime | None = None  # UTC
    ends_at: datetime | None = None  # UTC, dinormalisasi ke 23:59:59 WIB bila hanya tanggal
    recurring_rule: str | None = None  # mis. FREQ=WEEKLY;BYDAY=FRI,SAT,SUN
    confidence: float = Field(default=0.5, ge=0, le=1)
