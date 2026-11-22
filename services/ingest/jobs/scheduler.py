"""Scheduler Fase 0 (stub). Cron per konektor diaktifkan di vertical slice.

Jadwal default sumber resmi: tiap 6 jam. Expire job: tiap 10 menit.
Cleanup raw_items: harian 03:00 WIB. Semua konektor disabled di Fase 0 —
scheduler tidak menjalankan fetch apa pun sampai vertical slice BCA.
"""

from __future__ import annotations

SCHEDULES = {
    "expire": "*/10 * * * *",
    # Recheck 6 jam: promo TANPA ends_at dicek tiap jalan (6 jam, lebih sering —
    # pipeline/expire.py recheck_due), promo dengan ends_at tiap 24 jam
    # (kecuali segera berakhir: tiap 1 jam). Lihat ARCH §5.3 (A5).
    "recheck": "0 */6 * * *",
    "cleanup_raw_items": "0 3 * * *",  # 03:00 WIB — TTL raw_items 30 hari
    "sheets_flush": "setiap 30 detik (debounce) / 50 baris — lihat sync/sheets.py",
}


async def main() -> None:
    print("BuruPromo scheduler (Fase 0 stub): semua konektor disabled, tidak ada fetch.")
    print(f"Jadwal terdaftar: {SCHEDULES}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
