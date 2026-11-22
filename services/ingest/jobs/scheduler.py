"""Scheduler Fase 0 (stub). Cron per konektor diaktifkan di vertical slice.

Jadwal default sumber resmi: tiap 6 jam. Expire job: tiap 10 menit.
Cleanup raw_items: harian 03:00 WIB. Semua konektor disabled di Fase 0 —
scheduler tidak menjalankan fetch apa pun sampai vertical slice BCA.
"""

from __future__ import annotations

SCHEDULES = {
    "expire": "*/10 * * * *",
    "recheck": "0 */6 * * *",
    "cleanup_raw_items": "0 3 * * *",  # 03:00 WIB — TTL raw_items 30 hari
}


async def main() -> None:
    print("BuruPromo scheduler (Fase 0 stub): semua konektor disabled, tidak ada fetch.")
    print(f"Jadwal terdaftar: {SCHEDULES}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
