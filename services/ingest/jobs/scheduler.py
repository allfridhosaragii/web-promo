"""Scheduler BuruPromo — Vertical Slice BCA aktif (ARCH §5.3).

Jadwal default sumber resmi: tiap 6 jam. Expire job: tiap 10 menit.
Cleanup raw_items: harian 03:00 WIB (TTL 30 hari).
"""

from __future__ import annotations

import asyncio
import logging

from jobs.run_once import run_bca_once

logger = logging.getLogger("burupromo.scheduler")

SCHEDULES = {
    "bca_fetch": "0 */6 * * *",
    "expire": "*/10 * * * *",
    "recheck": "0 */6 * * *",
    "cleanup_raw_items": "0 3 * * *",  # 03:00 WIB — TTL raw_items 30 hari
    "sheets_flush": "setiap 30 detik (debounce) / 50 baris — lihat sync/sheets.py",
}


async def main() -> None:
    logger.info("BuruPromo scheduler aktif. Jadwal: %s", SCHEDULES)
    while True:
        try:
            await run_bca_once()
        except Exception:
            logger.exception("Siklus BCA gagal")
        await asyncio.sleep(6 * 3600)


if __name__ == "__main__":
    asyncio.run(main())
