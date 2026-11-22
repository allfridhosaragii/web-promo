"""Sinkron Google Spreadsheet — cermin otomatis (ARCH §17, revisi 2).

Postgres tetap sumber kebenaran. Spreadsheet hanya cermin: kalau sync gagal,
web + Postgres + Meilisearch tetap jalan. Jangan pernah membaca promo dari
Spreadsheet untuk ditampilkan di web.
"""

from sync.sheets import SheetsSync, build_sheets_client, promo_to_row

__all__ = ["SheetsSync", "build_sheets_client", "promo_to_row"]
