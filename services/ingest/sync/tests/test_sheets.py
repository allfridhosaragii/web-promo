"""Test sinkron Spreadsheet — mock Sheets API, TANPA request live,
tanpa kredensial asli (ARCH §17 + perbaikan E).

Perbaikan E: "Promo Aktif" ditulis ulang PENUH tiap sinkron (rewrite_sheet
dalam 1 batchUpdate) — JANGAN hapus baris satu-satu (nomor baris bergeser).
"Arsip" & "Log Sinkron" tetap append dengan cek id.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sync.sheets import (
    BACKOFF_SECONDS,
    SHEET_ACTIVE,
    SHEET_ARCHIVE,
    SheetsRateLimited,
    SheetsSync,
    promo_to_row,
)


def _promo(**overrides):
    promo = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Diskon 50% Kopi",
        "brand_name": "Kopi SBY",
        "category_names": ["Makanan & Minuman"],
        "promo_type": "persen",
        "value_percent": 50,
        "voucher_code": "KOPI50",
        "payment_methods": ["GoPay"],
        "region_codes": ["35.78"],
        "region_label": "Surabaya",
        "starts_at": datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 11, 30, 16, 59, 59, tzinfo=UTC),
        "status": "aktif",
        "source_url": "https://example.test/promo",
        "last_checked_at": datetime(2026, 11, 22, 3, 0, tzinfo=UTC),
    }
    promo.update(overrides)
    return promo


class FakeSheetsClient:
    """Sheets in-memory: {nama_sheet: [baris]}. Baris pertama = header (baris 1),
    data mulai baris 2 — sama seperti sheet asli (ARCH §17.2)."""

    def __init__(self, fail_times: int = 0) -> None:
        from sync.sheets import HEADERS_ACTIVE, HEADERS_ARCHIVE, HEADERS_LOG

        self.sheets: dict[str, list[list[str]]] = {
            SHEET_ACTIVE: [HEADERS_ACTIVE],
            SHEET_ARCHIVE: [HEADERS_ARCHIVE],
            "Log Sinkron": [HEADERS_LOG],
        }
        self.fail_times = fail_times
        self.rewrite_calls = 0
        self.failures = 0

    def _maybe_fail(self) -> None:
        if self.failures < self.fail_times:
            self.failures += 1
            raise SheetsRateLimited("429 Quota exceeded")

    def get_ids(self, sheet: str) -> list[str]:
        # Seperti range A2:A di client asli: header (baris 1) dilewati.
        return [row[0] for row in self.sheets[sheet][1:] if row and row[0]]

    def rewrite_sheet(self, sheet: str, rows: list[list[str]]) -> None:
        self._maybe_fail()
        self.rewrite_calls += 1
        # Tulis ulang penuh: isi lama hilang seluruhnya (termasuk ekor basi).
        self.sheets[sheet] = [list(r) for r in rows]

    def append_rows(self, sheet: str, rows) -> None:
        self._maybe_fail()
        self.sheets[sheet].extend(rows)


def _sync(client: FakeSheetsClient, **kwargs) -> SheetsSync:
    return SheetsSync(
        spreadsheet_id="spreadsheet-test",
        client=client,
        sleep_fn=lambda s: None,  # jangan tidur betulan di test
        **kwargs,
    )


def test_promo_to_row_columns_and_wib_format() -> None:
    row = promo_to_row(_promo())
    assert row[0] == "11111111-1111-1111-1111-111111111111"
    assert row[1] == "Diskon 50% Kopi"
    assert row[4] == "50%"
    assert row[5] == "KOPI50"
    assert row[7] == "Surabaya"
    assert row[9] == "2026-11-30 23:59 WIB"  # 16:59 UTC = 23:59 WIB
    assert row[10] == "aktif"
    assert len(row) == 13


def test_full_rewrite_upsert_same_id_no_duplicate() -> None:
    client = FakeSheetsClient()
    sync = _sync(client)
    sync.queue_upsert(_promo())
    sync.flush()
    assert len(client.sheets[SHEET_ACTIVE]) == 2  # header + 1 data
    sync.queue_upsert(_promo(title="Diskon 50% Kopi — Updated"))
    sync.flush()
    assert len(client.sheets[SHEET_ACTIVE]) == 2
    assert client.sheets[SHEET_ACTIVE][1][1] == "Diskon 50% Kopi — Updated"
    assert client.rewrite_calls == 2  # tiap flush = 1 rewrite penuh


def test_full_rewrite_shrinking_set_leaves_no_stale_rows() -> None:
    # Regresi E: dulu hapus baris satu-satu -> nomor bergeser -> duplikat/basi.
    client = FakeSheetsClient()
    sync = _sync(client)
    sync.queue_upsert(_promo(id="id-1", title="Promo 1"))
    sync.queue_upsert(_promo(id="id-2", title="Promo 2"))
    sync.flush()
    assert len(client.sheets[SHEET_ACTIVE]) == 3  # header + 2
    sync.queue_archive(_promo(id="id-2", title="Promo 2", status="kedaluwarsa"), "kedaluwarsa")
    sync.flush()
    active = client.sheets[SHEET_ACTIVE]
    assert len(active) == 2  # header + 1 — Promo 2 HILANG, tidak ada baris basi
    assert active[1][0] == "id-1"
    assert len(client.sheets[SHEET_ARCHIVE]) == 2
    assert client.sheets[SHEET_ARCHIVE][1][-1] == "kedaluwarsa"


def test_batch_many_promos_one_rewrite() -> None:
    client = FakeSheetsClient()
    sync = _sync(client)
    for i in range(3):
        sync.queue_upsert(_promo(id=f"id-{i}", title=f"Promo {i}"))
    sync.flush()
    assert client.rewrite_calls == 1  # 3 promo = 1 rewrite (hemat kuota)
    assert len(client.sheets[SHEET_ACTIVE]) == 4  # header + 3 data


def test_archive_is_idempotent() -> None:
    client = FakeSheetsClient()
    sync = _sync(client)
    sync.queue_upsert(_promo())
    sync.flush()
    sync.queue_archive(_promo(status="kedaluwarsa"), reason="kedaluwarsa")
    sync.flush()
    sync.queue_archive(_promo(status="kedaluwarsa"), reason="kedaluwarsa")
    sync.flush()
    assert len(client.sheets[SHEET_ARCHIVE]) == 2  # header + 1, tidak duplikat


def test_rebuild_active_from_postgres() -> None:
    client = FakeSheetsClient()
    sync = _sync(client)
    sync.rebuild_active([_promo(id="id-1"), _promo(id="id-2")])
    sync.flush()
    assert sync.active_count == 2
    assert len(client.sheets[SHEET_ACTIVE]) == 3


def test_retry_backoff_then_success_on_429() -> None:
    client = FakeSheetsClient(fail_times=2)
    delays: list[float] = []
    sync = SheetsSync(
        spreadsheet_id="spreadsheet-test",
        client=client,
        sleep_fn=lambda s: delays.append(s),
    )
    sync.queue_upsert(_promo())
    sync.flush()
    assert len(client.sheets[SHEET_ACTIVE]) == 2  # header + 1 data
    assert len(delays) == 2
    assert delays[0] >= BACKOFF_SECONDS[0] and delays[1] >= BACKOFF_SECONDS[1]
    assert sync.last_error is None


def test_persistent_429_goes_to_sheets_queue_after_5_attempts() -> None:
    client = FakeSheetsClient(fail_times=99)
    sync = _sync(client)
    sync.queue_upsert(_promo())
    sync.flush()
    assert len(client.sheets[SHEET_ACTIVE]) == 1  # tinggal header, tidak ada data
    assert len(sync.queued) == 1
    assert sync.queued[0]["action"] == "upsert"
    assert "429" in (sync.last_error or "")
    # Catatan: saat API 429 terus-menerus, tulis ke sheet "Log Sinkron" pun
    # gagal (API-nya mati) — auditnya ada di tabel Postgres sync_log, bukan
    # di sheet. Yang penting: item masuk antrean, tidak hilang.


def test_build_client_without_key_file_raises() -> None:
    from sync.sheets import build_sheets_client

    try:
        build_sheets_client("x", service_account_path="/tidak/ada/key.json")
    except RuntimeError as exc:
        assert "GOOGLE_SERVICE_ACCOUNT_JSON_PATH" in str(exc)
    else:
        raise AssertionError("seharusnya raise RuntimeError tanpa file key")
