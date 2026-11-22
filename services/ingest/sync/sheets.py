"""Sinkron Google Spreadsheet — cermin otomatis (ARCH §17, revisi 2 + perbaikan E).

Urutan wajib: upsert Postgres -> index Meilisearch -> sinkron Sheets ->
revalidate web. Kalau Sheets gagal, Postgres + Meilisearch TIDAK di-rollback.

Aturan keras (perbaikan E):
- Sheet "Promo Aktif" DITULIS ULANG PENUH tiap sinkron (clear + write dalam
  SATU values.batchUpdate, debounce 30 detik). JANGAN hapus baris satu-satu —
  nomor baris bergeser dan bikin duplikat. Worker menyimpan registry promo
  aktif in-memory (id -> promo) dan menulis ulang seluruh isinya; saat worker
  start, registry dibangun ulang dari Postgres (rebuild_active).
- "Arsip" & "Log Sinkron" tetap append, dengan cek `id` dulu (idempotent).
- Batch: kumpulkan 30 detik / 50 baris, lalu SATU batchUpdate per sheet.
- Kena 429 -> backoff 2/4/8/16/32 dtk (maks 5x, dengan jitter kecil),
  lalu masuk sheets_queue (Redis di prod, list in-memory di sini).
- Auth: service account Google, JSON key di env
  GOOGLE_SERVICE_ACCOUNT_JSON_PATH — JANGAN commit file key ke repo.
  Service account tidak punya billing account (proyek yang sama dengan Gemini).
- Batas yang mengikat: 60 tulis/menit/user (service account = satu user).
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")

SHEET_ACTIVE = "Promo Aktif"
SHEET_ARCHIVE = "Arsip"
SHEET_LOG = "Log Sinkron"

HEADERS_ACTIVE = [
    "id", "judul", "brand", "kategori", "nilai_diskon", "kode",
    "metode_bayar", "wilayah", "mulai", "berakhir_WIB", "status",
    "sumber_URL", "terakhir_dicek",
]
HEADERS_ARCHIVE = [*HEADERS_ACTIVE, "alasan_arsip"]
HEADERS_LOG = ["waktu_WIB", "promo_id", "aksi", "status", "detail"]

BATCH_WINDOW_SECONDS = 30
BATCH_MAX_ROWS = 50
ID_CACHE_TTL_SECONDS = 300  # 5 menit (ARCH §17.3)
BACKOFF_SECONDS = (2, 4, 8, 16, 32)  # maks 5x
MAX_ATTEMPTS = 5

SHEETS_QUEUE_KEY = "sheets_queue"


class SheetsRateLimited(Exception):
    """429 dari Sheets API — retry dengan backoff."""


class SheetsClient(Protocol):
    """Protokol minimal yang dipakai SheetsSync. Client nyata (googleapiclient)
    dan Fake di test sama-sama memenuhi ini — sync tidak pernah import
    googleapiclient di level modul, hanya di build_sheets_client()."""

    def get_ids(self, sheet: str) -> list[str]:
        """Kolom `id` sheet target (tanpa header)."""

    def rewrite_sheet(self, sheet: str, rows: list[list[str]]) -> None:
        """Tulis ulang SELURUH sheet (termasuk header) dalam SATU batchUpdate.
        Baris lama yang tidak ada di `rows` harus hilang (ditindih baris kosong).
        Dipakai untuk 'Promo Aktif' — JANGAN hapus baris satu-satu."""

    def append_rows(self, sheet: str, rows: list[list[str]]) -> None:
        """Append baris ke akhir sheet (dipakai 'Arsip' & 'Log Sinkron')."""


def format_wib(value: datetime | str | None) -> str:
    """Datetime UTC -> 'YYYY-MM-DD HH:mm WIB' (teks, bukan serial date Sheets)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.astimezone(WIB).strftime("%Y-%m-%d %H:%M WIB")


def format_nilai(promo: dict) -> str:
    """Nilai diskon sebagai teks yang tampil, mis. '50%', 'Rp15.000', 'Gratis ongkir'."""
    if promo.get("promo_type") == "gratis_ongkir":
        return "Gratis ongkir"
    if promo.get("value_percent") is not None:
        return f"{promo['value_percent']:g}%"
    if promo.get("value_amount") is not None:
        return f"Rp{int(promo['value_amount']):,}".replace(",", ".")
    if promo.get("promo_type") == "cashback":
        return "Cashback"
    return ""


def promo_to_row(promo: dict, archive_reason: str | None = None) -> list[str]:
    """Satu promo -> satu baris sheet, urutan kolom = HEADERS_ACTIVE (+ alasan_arsip)."""
    categories = promo.get("category_names") or promo.get("category_slugs") or []
    payments = promo.get("payment_methods") or []
    regions = promo.get("region_codes") or []
    region = promo.get("region_label") or (", ".join(regions) if regions else "Nasional")
    row = [
        str(promo.get("id", "")),
        str(promo.get("title", "")),
        str(promo.get("brand_name") or promo.get("brand") or ""),
        ", ".join(categories),
        format_nilai(promo),
        str(promo.get("voucher_code") or ""),
        ", ".join(payments),
        region,
        format_wib(promo.get("starts_at")),
        format_wib(promo.get("ends_at")),
        str(promo.get("status", "")),
        str(promo.get("source_url", "")),
        format_wib(promo.get("last_checked_at")),
    ]
    if archive_reason is not None:
        row.append(archive_reason)
    return row


@dataclass
class PendingArchive:
    promo: dict
    reason: str


@dataclass
class SheetsSync:
    """Registry promo aktif + flush batch + retry backoff + antrean.

    `revalidate_fn` (opsional): dipanggil setelah flush sukses — worker
    mengisinya dengan pipeline.revalidate.trigger_revalidate (ARCH §17.4).
    """

    spreadsheet_id: str
    client: SheetsClient
    redis_client: object | None = None  # redis.Redis bila tersedia; None = in-memory
    sleep_fn: Callable[[float], None] = time.sleep
    revalidate_fn: Callable[[], bool] | None = None
    _active: dict[str, dict] = field(default_factory=dict)  # id -> promo aktif
    _archive_pending: list[PendingArchive] = field(default_factory=list)
    _dirty_active: bool = False
    _last_flush_at: float = field(default_factory=time.time)
    _id_cache: dict[str, dict[str, int]] = field(default_factory=dict)
    _id_cache_at: dict[str, float] = field(default_factory=dict)
    queued: list[dict] = field(default_factory=list)  # sheets_queue in-memory
    last_success_at: datetime | None = None
    last_error: str | None = None

    # -- antrean publik -------------------------------------------------
    def rebuild_active(self, promos: list[dict]) -> None:
        """Bangun ulang registry dari Postgres (dipanggil saat worker start).
        Tanpa ini, restart worker akan menulis ulang sheet Aktif menjadi kosong."""
        self._active = {str(p["id"]): p for p in promos if p.get("id")}
        self._dirty_active = True

    def queue_upsert(self, promo: dict) -> None:
        self._active[str(promo["id"])] = promo
        self._dirty_active = True
        self._maybe_flush()

    def queue_archive(self, promo: dict, reason: str) -> None:
        self._active.pop(str(promo.get("id", "")), None)
        self._dirty_active = True
        self._archive_pending.append(PendingArchive(promo=promo, reason=reason))
        self._maybe_flush()

    @property
    def pending_count(self) -> int:
        return len(self._active) + len(self._archive_pending)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def _maybe_flush(self) -> None:
        if len(self._archive_pending) >= BATCH_MAX_ROWS:
            self.flush()
        elif time.time() - self._last_flush_at >= BATCH_WINDOW_SECONDS and (
            self._dirty_active or self._archive_pending
        ):
            self.flush()

    def flush_if_due(self) -> None:
        """Dipanggil scheduler tiap detik / tiap loop: flush bila jendela 30 dtk lewat."""
        if (self._dirty_active or self._archive_pending) and (
            time.time() - self._last_flush_at >= BATCH_WINDOW_SECONDS
        ):
            self.flush()

    # -- inti ------------------------------------------------------------
    def _get_id_map(self, sheet: str) -> dict[str, int]:
        """id -> nomor baris (1-based, header baris 1). Cache 5 menit.
        Dipakai HANYA untuk cek id di Arsip/Log (append), bukan untuk Aktif."""
        now = time.time()
        cached_at = self._id_cache_at.get(sheet, 0)
        if sheet in self._id_cache and now - cached_at < ID_CACHE_TTL_SECONDS:
            return self._id_cache[sheet]
        ids = self.client.get_ids(sheet)
        mapping = {promo_id: i + 2 for i, promo_id in enumerate(ids)}  # baris 2 = data pertama
        self._id_cache[sheet] = mapping
        self._id_cache_at[sheet] = now
        return mapping

    def _redis(self, cmd: str, *args) -> object | None:
        if self.redis_client is None:
            return None
        return getattr(self.redis_client, cmd)(*args)

    def _enqueue_failed(self, items: list[dict], error: str) -> None:
        payloads = [
            {"promo_id": it.get("promo_id"), "action": it.get("action"), "error": error}
            for it in items
        ]
        if self.redis_client is not None:
            for payload in payloads:
                self._redis("rpush", SHEETS_QUEUE_KEY, json.dumps(payload))
        else:
            self.queued.extend(payloads)

    def _log(self, promo_id: str, action: str, status: str, detail: str) -> None:
        """Append ke sheet 'Log Sinkron'. Gagal log tidak boleh menggagalkan sync."""
        try:
            now_wib = datetime.now(UTC).astimezone(WIB).strftime("%Y-%m-%d %H:%M WIB")
            self.client.append_rows(SHEET_LOG, [[now_wib, promo_id, action, status, detail[:200]]])
        except Exception:
            pass

    def flush(self) -> None:
        """Tulis ulang 'Promo Aktif' penuh + append 'Arsip' yang tertunda."""
        if not self._dirty_active and not self._archive_pending:
            return
        self._last_flush_at = time.time()
        try:
            if self._dirty_active:
                rows = [HEADERS_ACTIVE] + [
                    promo_to_row(promo) for promo in self._active.values()
                ]
                self._call_with_retry(lambda: self.client.rewrite_sheet(SHEET_ACTIVE, rows))
                self._id_cache.pop(SHEET_ACTIVE, None)
                self._dirty_active = False
                self._log("", "rewrite_aktif", "ok", f"{len(rows) - 1} promo aktif ditulis ulang")
            if self._archive_pending:
                self._flush_archive()
            self.last_success_at = datetime.now(UTC)
            self.last_error = None
            if self.revalidate_fn is not None:
                try:
                    self.revalidate_fn()
                except Exception:
                    pass  # revalidate gagal tidak menggagalkan sync (ARCH §17.4)
        except SheetsRateLimited as exc:
            self.last_error = f"429 Sheets API: {exc}"
            failed = [{"promo_id": pid, "action": "upsert"} for pid in self._active]
            failed += [
                {"promo_id": str(a.promo.get("id", "")), "action": "archive"}
                for a in self._archive_pending
            ]
            self._enqueue_failed(failed, str(exc))
            self._log("", "retry", "antre", str(exc)[:200])
        except Exception as exc:  # noqa: BLE001 — error lain dicatat, promo tetap tampil di web
            self.last_error = str(exc)

    def _flush_archive(self) -> None:
        """Append ke 'Arsip' dengan cek id dulu (idempotent, tanpa hapus baris)."""
        items, self._archive_pending = self._archive_pending, []
        archive_ids = self._get_id_map(SHEET_ARCHIVE)
        rows = []
        for item in items:
            promo_id = str(item.promo.get("id", ""))
            if promo_id and promo_id in archive_ids:
                continue  # sudah ada di Arsip — jangan duplikat
            rows.append(promo_to_row(item.promo, item.reason))
        if rows:
            self._call_with_retry(lambda: self.client.append_rows(SHEET_ARCHIVE, rows))
            self._id_cache.pop(SHEET_ARCHIVE, None)
        for item in items:
            self._log(str(item.promo.get("id", "")), "pindah_arsip", "ok", item.reason)

    def _call_with_retry(self, fn: Callable[[], None]) -> None:
        """Retry hanya untuk 429, backoff 2/4/8/16/32 dtk + jitter, maks 5x."""
        last_exc: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                fn()
                return
            except SheetsRateLimited as exc:
                last_exc = exc
                if attempt < MAX_ATTEMPTS - 1:
                    delay = BACKOFF_SECONDS[attempt] + random.uniform(0, 1)
                    self.sleep_fn(delay)
        assert last_exc is not None
        raise last_exc

    def status(self) -> dict:
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "active_count": len(self._active),
            "pending_archive": len(self._archive_pending),
            "queued_count": len(self.queued),
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error": self.last_error,
        }


def build_sheets_client(spreadsheet_id: str, service_account_path: str | None = None):
    """Bangun client Sheets API asli (service account). Lazy import — modul ini
    tetap bisa di-test tanpa google-api-python-client terpasang.

    Raises RuntimeError bila file key tidak ada — JANGAN commit JSON key ke repo.
    """
    path = service_account_path or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "")
    if not path or not os.path.exists(path):
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON_PATH belum diisi / file tidak ada. "
            "Isi path ke JSON service account (di luar repo) dan share spreadsheet "
            "ke email service account sebagai Editor. Tanpa ini, sinkron nonaktif."
        )
    # Import di sini supaya `import sync.sheets` tidak butuh kredensial / library Google.
    from google.oauth2 import service_account  # type: ignore[import-not-found]
    from googleapiclient.discovery import build  # type: ignore[import-not-found]

    creds = service_account.Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _GoogleSheetsClient(service, spreadsheet_id)


def _col_letter(n: int) -> str:
    """1 -> A, 13 -> M, 27 -> AA."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


class _GoogleSheetsClient:
    """Adapter tipis googleapiclient -> protokol SheetsClient."""

    def __init__(self, service, spreadsheet_id: str) -> None:
        self._service = service
        self._spreadsheet_id = spreadsheet_id

    def _values(self):
        return self._service.spreadsheets().values()

    def get_ids(self, sheet: str) -> list[str]:
        try:
            res = self._values().get(
                spreadsheetId=self._spreadsheet_id, range=f"'{sheet}'!A2:A"
            ).execute()
            return [row[0] for row in res.get("values", []) if row]
        except Exception as exc:
            if "429" in str(exc):
                raise SheetsRateLimited(str(exc)) from exc
            raise

    def rewrite_sheet(self, sheet: str, rows: list[list[str]]) -> None:
        """Tulis ulang penuh dalam SATU values.batchUpdate: range A1:<kolom><baris>
        mencakup baris lama juga — ekor lama yang lebih panjang ditindih baris
        kosong supaya tidak ada baris basi yang tertinggal. (Sheets API tidak
        punya satu call clear+write; ini satu batchUpdate, bukan hapus per baris.)"""
        try:
            old = self._values().get(
                spreadsheetId=self._spreadsheet_id, range=f"'{sheet}'!A:A"
            ).execute().get("values", [])
            n_cols = max((len(r) for r in rows), default=1)
            total = max(len(rows), len(old))
            padded = [list(r) + [""] * (n_cols - len(r)) for r in rows]
            padded += [[""] * n_cols for _ in range(total - len(rows))]
            last_col = _col_letter(n_cols)
            self._values().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": [{"range": f"'{sheet}'!A1:{last_col}{total}", "values": padded}],
                },
            ).execute()
        except SheetsRateLimited:
            raise
        except Exception as exc:
            if "429" in str(exc):
                raise SheetsRateLimited(str(exc)) from exc
            raise

    def append_rows(self, sheet: str, rows: list[list[str]]) -> None:
        try:
            self._values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{sheet}'!A1",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()
        except Exception as exc:
            if "429" in str(exc):
                raise SheetsRateLimited(str(exc)) from exc
            raise
