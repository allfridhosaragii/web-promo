# services/ingest — BuruPromo ingestion (Python 3.12+)

Pipeline (ARCHITECTURE.md §5): Scheduler → Connector.fetch → raw_items →
normalize → OCR → classifier → extract (aturan dulu, LLM bila perlu) →
normalize tanggal (WIB) → geotag → categorize → dedup → score →
upsert Postgres → index Meilisearch → sinkron Spreadsheet (§17) →
revalidate web via HTTP (§17.4).

## Fase 0 — yang ada di sini

- `connectors/base.py` — `BaseConnector` (ABC, §5.1): `fetch()`, `parse()`,
  `health_check()`, rate limit ≤1 req/detik/domain + retry bawaan, robots.txt,
  URL kanonis (strip UTM / `__cf_chl_*`), hash konten. `RawItem` memakai
  `kw_only=True` — konstruksi wajib pakai keyword.
- `connectors/bank_bca.py` — **stub saja, disabled.** `fetch()` menolak dengan
  `NotImplementedError` sampai vertical slice BCA. Fixture placeholder ada di
  `connectors/tests/fixtures/bank_bca/` (bukan data live).
- `pipeline/rules.py` — ekstraksi berbasis aturan (regex tanggal, nilai, kode,
  pola berulang). Jalan SEBELUM LLM — hemat kuota free tier.
- `pipeline/llm.py` + `pipeline/llm_config.py` — QuotaGuard + LLMConfig
  (ARCH §11.1, ADR 0004). **Revisi 2: TANPA billing account, TANPA budget
  berbasis USD.** Model dipilih owner dari AI Studio (`.env` LLM_MODEL;
  kosong = LLM nonaktif). Limit dari `.env`: LLM_RPM,
  LLM_DAILY_REQUEST_LIMIT, LLM_TPM. **Tanpa `GEMINI_API_KEY` atau tanpa
  `LLM_MODEL`, tidak ada panggilan API** — hasil aturan + antrean manual.
  Kena 429 (RPD) -> sisa masuk `llm_queue`, proses ulang setelah reset PT.
- `pipeline/expire.py` — lifecycle dihitung dari tanggal
  (`dijadwalkan|aktif|segera_berakhir|kedaluwarsa`); `recurring_rule` adalah
  RRULE valid (JSM `FREQ=WEEKLY;BYDAY=FR,SA,SU`, Jumat `BYDAY=FR`, payday
  `FREQ=MONTHLY;BYMONTHDAY=25`); promo tanpa `ends_at` ("Tanpa batas waktu")
  recheck tiap 6 jam + auto-kedaluwarsa bila tak terkonfirmasi 14 hari;
  TTL `raw_items` 30 hari.
- `pipeline/index.py` — dokumen Meilisearch: `starts_at_ts`/`ends_at_ts`
  (Unix detik) untuk filter/sort, `lifecycle` + `moderation` terpisah.
  Index utama hanya lifecycle aktif/segera_berakhir + moderation != ditolak.
- `sync/sheets.py` — sinkron Google Spreadsheet (§17): sheet "Promo Aktif"
  ditulis ulang PENUH tiap sinkron (1 batchUpdate, debounce 30 dtk);
  "Arsip" & "Log Sinkron" append dengan cek id. Service account via env,
  JANGAN commit JSON key. Tabel audit: `sync_log` (Postgres).
- `pipeline/revalidate.py` — pemicu revalidate web via HTTP
  (POST /api/revalidate, header `x-revalidate-secret`). Gagal revalidate
  tidak menggagalkan pipeline.
- `jobs/` — scheduler + expire job (stub Fase 0, jalan penuh di vertical slice).

## Aturan keras

- `fetch()` hanya dari URL di `docs/SOURCES.md` yang sudah terverifikasi.
- Dilarang: bypass login/captcha, `/api/` internal yang di-Disallow
  (AZKO, Klik Indomaret), crawl sumber `disabled` (Alfamart, Alfamidi, X).
- Fixture test **wajib** per konektor: `make check-fixtures`.
- X: budget $0, disabled sampai Fase 2.

## Jalankan

```bash
cd services/ingest
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
python3 scripts/check_fixtures.py
```
