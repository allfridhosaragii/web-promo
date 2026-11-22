"""Pemicu revalidate web via HTTP (ARCH §17.4, perbaikan F).

Hono (API) tidak bisa memanggil revalidatePath Next.js langsung. Jadi
worker ingest / API memanggil route handler Next.js POST /api/revalidate
dengan secret di header `x-revalidate-secret` (env REVALIDATE_SECRET).

Gagal revalidate TIDAK menggagalkan pipeline dan TIDAK memblokir Sheets sync:
web tetap update saat ISR berikutnya. Kembalikan False + log, bukan raise.
"""

from __future__ import annotations

import os

import httpx

REVALIDATE_PATH = "/api/revalidate"


def trigger_revalidate(
    web_base_url: str | None = None,
    secret: str | None = None,
    paths: list[str] | None = None,
    tags: list[str] | None = None,
    client: httpx.Client | None = None,
) -> bool:
    """POST /api/revalidate. True bila web mengembalikan 200."""
    base = (web_base_url or os.environ.get("WEB_BASE_URL", "") or "").rstrip("/")
    token = secret if secret is not None else os.environ.get("REVALIDATE_SECRET", "")
    if not base or not token:
        return False
    payload = {"paths": paths or ["/"], "tags": tags or ["promos"]}
    headers = {"x-revalidate-secret": token}
    try:
        if client is not None:
            resp = client.post(f"{base}{REVALIDATE_PATH}", json=payload, headers=headers)
        else:
            with httpx.Client(timeout=10.0) as http:
                resp = http.post(f"{base}{REVALIDATE_PATH}", json=payload, headers=headers)
        return resp.status_code == 200
    except Exception:
        return False
