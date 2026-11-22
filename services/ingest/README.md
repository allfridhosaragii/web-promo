# services/ingest — BuruPromo ingestion (Python 3.12+)

Pipeline (ARCHITECTURE.md §5): Scheduler → Connector.fetch → raw_items →
normalize → OCR → classifier → extract LLM → normalize tanggal (WIB) →
geotag → categorize → dedup → score → upsert Postgres → index Meilisearch.

## Fase 0 — yang ada di sini

- `connectors/base.py` — `BaseConnector` (ABC, §5.1): `fetch()`, `parse()`,
  `health_check()`, rate limit ≤1 req/detik/domain + retry bawaan, robots.txt,
  URL kanonis (strip UTM / `__cf_chl_*`), hash konten.
- `connectors/bank_bca.py` — **stub saja, disabled.** `fetch()` menolak dengan
  `NotImplementedError` sampai vertical slice BCA. Fixture placeholder ada di
  `connectors/tests/fixtures/bank_bca/` (bukan data live).
- `pipeline/llm.py` — interface LLM Gemini 2.5 Flash-Lite + `BudgetGuard`
  ($5/bulan, $0,16/hari, peringatan $4). **Tanpa `GEMINI_API_KEY`, tidak ada
  panggilan API berbayar — ekstraksi masuk antrean manual.**
- `pipeline/expire.py` — `segera_berakhir` = `ends_at` < 24 jam; promo berulang
  (mis. JSM `FREQ=WEEKLY;BYDAY=FRI,SAT,SUN`) dibuat kemunculan berikutnya;
  TTL `raw_items` 30 hari.
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
