"""Sinkron Google Spreadsheet — cermin otomatis (ARCH §17, revisi 2).

Urutan wajib: upsert Postgres -> index Meilisearch -> sinkron Sheets ->
revalidate web. Kalau Sheets gagal, Postgres + Meilisearch TIDAK di-rollback.

Aturan keras:
- Upsert berdasarkan kolom `id` — jangan duplikat baris. Baca kolom id
  sekali, cache di Redis 5 menit (di sini: cache in-memory + Redis opsional).
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

    def batch_update(self, sheet: str, updates: dict[int, list[str]], appends: list[list[str]]) -> None:
        """Update baris yang sudah ada (row number 1-based, header = baris 1)
        + append baris baru — dalam SATU request batchUpdate."""

    def delete_rows(self, sheet: str, rows: list[int]) -> None:
        """Hapus baris (row number 1-based)."""

    def append_rows(self, sheet: str, rows: list[list[str]]) -> None:
        """Append baris ke akhir sheet."""


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
class PendingItem:
    promo: dict
    action: str  # "upsert" | "archive"
    archive_reason: str | None = None


@dataclass
class SheetsSync:
    """Buffer + flush batch + retry backoff + antrean. Satu instance per worker."""

    spreadsheet_id: str
    client: SheetsClient
    redis_client: object | None = None  # redis.Redis bila tersedia; None = in-memory
    sleep_fn: Callable[[float], None] = time.sleep
    _pending: list[PendingItem] = field(default_factory=list)
    _last_flush_at: float = field(default_factory=time.time)
    _id_cache: dict[str, dict[str, int]] = field(default_factory=dict)
    _id_cache_at: dict[str, float] = field(default_factory=dict)
    queued: list[dict] = field(default_factory=list)  # sheets_queue in-memory
    last_success_at: datetime | None = None
    last_error: str | None = None

    # -- antrean publik -------------------------------------------------
    def queue_upsert(self, promo: dict) -> None:
        self._pending.append(PendingItem(promo=promo, action="upsert"))
        self._maybe_flush()

    def queue_archive(self, promo: dict, reason: str) -> None:
        self._pending.append(PendingItem(promo=promo, action="archive", archive_reason=reason))
        self._maybe_flush()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def _maybe_flush(self) -> None:
        if len(self._pending) >= BATCH_MAX_ROWS:
            self.flush()
        elif time.time() - self._last_flush_at >= BATCH_WINDOW_SECONDS and self._pending:
            self.flush()

    def flush_if_due(self) -> None:
        """Dipanggil scheduler tiap detik / tiap loop: flush bila jendela 30 dtk lewat."""
        if self._pending and time.time() - self._last_flush_at >= BATCH_WINDOW_SECONDS:
            self.flush()

    # -- inti ------------------------------------------------------------
    def _get_id_map(self, sheet: str) -> dict[str, int]:
        """id -> nomor baris (1-based, header baris 1). Cache 5 menit."""
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

    def _enqueue_failed(self, items: list[PendingItem], error: str) -> None:
        payloads = [
            {"promo_id": it.promo.get("id"), "action": it.action, "error": error}
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
        """Kirim semua pending dalam batch per sheet. Idempotent: cek id dulu."""
        if not self._pending:
            return
        items, self._pending = self._pending, []
        self._last_flush_at = time.time()
        by_sheet: dict[str, list[PendingItem]] = {}
        for item in items:
            sheet = SHEET_ARCHIVE if item.action == "archive" else SHEET_ACTIVE
            by_sheet.setdefault(sheet, []).append(item)
        for sheet, sheet_items in by_sheet.items():
            self._flush_sheet(sheet, sheet_items)

    def _flush_sheet(self, sheet: str, items: list[PendingItem]) -> None:
        try:
            id_map = self._get_id_map(sheet)
            updates: dict[int, list[str]] = {}
            appends: list[list[str]] = []
            for item in items:
                row = promo_to_row(item.promo, item.archive_reason if sheet == SHEET_ARCHIVE else None)
                promo_id = str(item.promo.get("id", ""))
                if promo_id and promo_id in id_map:
                    updates[id_map[promo_id]] = row
                else:
                    appends.append(row)
            self._call_with_retry(
                lambda: self.client.batch_update(sheet, updates, appends)
            )
            # Sukses: refresh cache id (baris baru ikut terhitung).
            self._id_cache.pop(sheet, None)
            self.last_success_at = datetime.now(UTC)
            self.last_error = None
            for item in items:
                action = "pindah_arsip" if sheet == SHEET_ARCHIVE else "upsert"
                self._log(str(item.promo.get("id", "")), action, "ok", f"{sheet}: {len(updates)} update, {len(appends)} baru")
            if sheet == SHEET_ARCHIVE:
                # Hapus dari Promo Aktif setelah berhasil masuk Arsip.
                active_map = self._get_id_map(SHEET_ACTIVE)
                rows_to_delete = [
                    active_map[str(it.promo.get("id", ""))]
                    for it in items
                    if str(it.promo.get("id", "")) in active_map
                ]
                if rows_to_delete:
                    self._call_with_retry(
                        lambda: self.client.delete_rows(SHEET_ACTIVE, rows_to_delete)
                    )
                    self._id_cache.pop(SHEET_ACTIVE, None)
        except SheetsRateLimited as exc:
            self.last_error = f"429 Sheets API: {exc}"
            self._enqueue_failed(items, str(exc))
            for item in items:
                self._log(str(item.promo.get("id", "")), "retry", "antre", str(exc)[:200])
        except Exception as exc:  # noqa: BLE001 — error lain dicatat, promo tetap tampil di web
            self.last_error = str(exc)
            self._enqueue_failed(items, str(exc))

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
            "pending": len(self._pending),
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

    def batch_update(self, sheet: str, updates: dict[int, list[str]], appends: list[list[str]]) -> None:
        try:
            data = [
                {"range": f"'{sheet}'!A{row}", "values": [values]}
                for row, values in sorted(updates.items())
            ]
            if data:
                self._values().batchUpdate(
                    spreadsheetId=self._spreadsheet_id,
                    body={"valueInputOption": "RAW", "data": data},
                ).execute()
            if appends:
                self._values().append(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{sheet}'!A1",
                    valueInputOption="RAW",
                    body={"values": appends},
                ).execute()
        except Exception as exc:
            if "429" in str(exc):
                raise SheetsRateLimited(str(exc)) from exc
            raise

    def delete_rows(self, sheet: str, rows: list[int]) -> None:
        # Hapus dari nomor baris terbesar dulu supaya nomor baris lain tidak bergeser.
        try:
            requests = [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": self._sheet_id(sheet),
                            "dimension": "ROWS",
                            "startIndex": row - 1,
                            "endIndex": row,
                        }
                    }
                }
                for row in sorted(rows, reverse=True)
            ]
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id, body={"requests": requests}
            ).execute()
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

    def _sheet_id(self, sheet: str) -> int:
        meta = self._service.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == sheet:
                return s["properties"]["sheetId"]
        raise RuntimeError(f"Sheet '{sheet}' tidak ditemukan di spreadsheet.")
