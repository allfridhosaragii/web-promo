# ARCHITECTURE.md — BuruPromo

> Status: **REVISI 2 — SEMUA GRATIS (Rp0), disetujui owner 2026-11-22. Siap lanjut Fase 0.**
> Tanggal: 2026-11-22 (revisi 1: verifikasi SOURCES + interface konektor + skema Meilisearch + dataset wilayah + definisi expire + OpenAPI + fixture wajib + vertical slice BCA; revisi 2: semua Rp0 + Oracle Always Free + quota guard Gemini + sinkron Google Spreadsheet)
> APP_NAME: `BuruPromo` (satu konstanta, bisa diganti)
> Fokus awal: Jawa Timur, prioritas Surabaya Raya
> Target pengguna: mahasiswa & anak muda yang sensitif harga
> **Keputusan owner (2026-11-22, revisi 2 — menggantikan revisi 1): SEMUA HARUS GRATIS (Rp0), kecuali domain yang owner beli sendiri.** LLM = Gemini API FREE TIER saja via Google AI Studio, TANPA billing account, budget $5/bulan DIHAPUS, diganti quota guard. Hosting produksi = Oracle Cloud Always Free (VM ARM Ampere A1) + Caddy, semua Docker Compose di satu VM. JANGAN pakai Vercel Hobby. Cloudflare R2 diganti penyimpanan lokal di VM / Oracle Object Storage free tier. Backup DB harian ke Google Drive via rclone (gratis). Monitoring: Sentry free tier + Umami self-host di VM yang sama. X API = budget $0, tidak diaktifkan sampai Fase 2.

---

## 1. Ringkasan

BuruPromo adalah search engine khusus promo Indonesia. Pengguna mengetik "kopi", "gratis ongkir", "promo BCA", "bakso surabaya", atau memilih kategori + wilayah, lalu mendapat daftar promo yang **masih aktif**, lengkap, dan sebisa mungkin **terverifikasi**.

Bukan agregator yang menyalin postingan utuh. Sistem menyimpan **ringkasan terstruktur + link ke sumber + thumbnail kecil**, dengan skor kepercayaan dan voting komunitas.

Prinsip arsitektur:

1. **Konektor per sumber.** Tidak ada satu API "semua promo". Setiap sumber punya adapter sendiri, status sendiri, jadwal sendiri, budget sendiri, dan kill switch sendiri.
2. **Legal dulu, teknis kemudian.** Utamakan API resmi & feed afiliasi. Scraping hanya halaman publik tanpa login, hormati `robots.txt`, rate limit sopan, User-Agent jujur.
3. **Jangan mengarang promo.** Field yang tidak diketahui = `null`. Data dummy development wajib `is_seed=true` dan tidak masuk index produksi.
4. **Kedaluarsa itu fitur.** Promo lewat `ends_at` otomatis turun/hilang dari hasil utama. Semua waktu tampil WIB (`Asia/Jakarta`), simpan UTC di DB.
5. **Search adalah produk.** Meilisearch adalah sumber kebenaran untuk pencarian, Postgres adalah sumber kebenaran untuk data.
6. **Semua Rp0 — tidak ada jalur yang bisa menimbulkan tagihan.** Tidak ada billing account di Google Cloud (Gemini), tidak ada layanan berbayar di Oracle di luar jatah Always Free, tidak ada pay-as-you-go di Sentry. Kalau satu layanan kena batas free tier, job **berhenti / antre ulang**, bukan naik ke tier berbayar. Satu-satunya biaya yang diizinkan adalah domain, yang dibeli owner sendiri di luar sistem ini.

---

## 2. Monorepo

```
burupromo/
├─ apps/
│  ├─ web/                # Next.js App Router + TypeScript strict + PWA
│  └─ api/                # Hono + Zod + Drizzle
├─ services/
│  └─ ingest/             # Python 3.12+: konektor, pipeline, worker, cron
│     ├─ connectors/      # satu file per sumber
│     ├─ pipeline/        # normalize, ocr, extract_llm, geotag, dedup, score, index
│     ├─ schemas/         # Pydantic, cermin packages/contracts
│     └─ jobs/            # scheduler, expire, recheck, source-health
├─ packages/
│  ├─ contracts/          # Zod schema + tipe bersama (API <-> Web <-> Ingest)
│  ├─ db/                 # Drizzle schema + migrasi + seed wilayah
│  ├─ ui/                 # design system: token, komponen Radix-based
│  └─ config/             # tsconfig, biome, tailwind preset
├─ infra/                 # docker-compose, meilisearch settings, nginx
└─ docs/                  # ARCHITECTURE.md, SOURCES.md, ADR, runbook
```

Tooling:
- TypeScript: **Turborepo + pnpm**
- Python: **uv**
- Lint: Biome (TS), Ruff (Python)
- Test: Vitest, Playwright e2e, pytest
- CI: GitHub Actions — lint, typecheck, test, audit dependensi

---

## 3. Tech stack — kenapa dipilih

### 3.1 Frontend — `apps/web`

- **Next.js (App Router, stable terbaru) + React Server Components + TypeScript strict**
  Alasan: SEO untuk halaman `/promo/makanan/surabaya` dkk, ISR, dan RSC untuk halaman publik yang cepat.
- **Tailwind CSS + design token sendiri** (lihat §9). Komponen primitif **Radix UI**. Dilarang pakai tema shadcn mentah-mentah.
- **TanStack Query** untuk bagian interaktif, **nuqs** untuk filter di URL (filter bisa di-share lewat link).
- Search instan memanggil Meilisearch **lewat API sendiri**, jangan ekspos master key ke browser.
- **PWA**: installable, offline untuk promo tersimpan, Web Push, **Share Target** (lihat §7).
- Peta: **MapLibre GL** + tile gratis (OpenFreeMap / Protomaps).

Target: LCP < 1,8 detik di 4G HP menengah, JS awal halaman publik < 150 KB gzip, Lighthouse ≥ 95 (Fase 1 minimal ≥ 90).

### 3.2 API — `apps/api`

- **TypeScript + Hono** — ringan, cepat, bisa jalan di Node / Bun / edge.
- Validasi **Zod**, kontrak dibagikan via `packages/contracts`.
- ORM **Drizzle ORM** di atas PostgreSQL.
- Auth **Better Auth** — email magic link + Google. Peran: `user`, `moderator`, `admin`.

Endpoint inti (kontrak di `packages/contracts`, versi `/v1`):
- `GET /v1/promos?q=&category=&region=&brand=&payment=&type=&ends_today=&sort=&page=`
- `GET /v1/promos/:id`
- `POST /v1/promos/:id/vote` — masih berlaku / sudah habis
- `POST /v1/promos/:id/report`
- `POST /v1/submissions` — kirim promo komunitas
- `GET/POST /v1/saved-promos`, `GET/POST /v1/saved-searches`
- `GET/POST /v1/wallet` — Dompetku (Fase 3)
- `GET /v1/regions`, `GET /v1/categories`, `GET /v1/brands`
- `GET /admin/*` — hanya peran admin/moderator

### 3.3 Ingestion & AI — `services/ingest` (Python 3.12+)

Alasan Python: ekosistem scraping, OCR, dan NLP paling matang.

- HTTP: `httpx` (async) + `selectolax` untuk parsing HTML. **Playwright hanya** untuk halaman publik yang wajib render JS.
- OCR katalog gambar/PDF: **PaddleOCR** (bagus untuk teks Indonesia) atau Tesseract `ind`.
- Ekstraksi terstruktur: LLM dengan **JSON Schema / structured output**, provider bisa diganti lewat interface. **LLM = Gemini API FREE TIER saja via Google AI Studio, TANPA billing account — lihat §11.1. Tidak ada fallback berbayar.**
- **Hemat kuota LLM (wajib, karena free tier sangat kecil):** (1) ekstraksi berbasis aturan dulu (regex tanggal, nilai, kode) — LLM hanya untuk field yang tidak bisa diparse aturan; (2) batch: gabung beberapa promo sejenis dalam 1 call LLM bila model mengizinkan, bukan 1 promo = 1 call; (3) cache hasil ekstraksi per `content_hash` — konten sama tidak dipanggil ulang; (4) jangan panggil LLM untuk klasifikasi "apakah ini promo?" bila aturan cepat sudah bisa menjawab.
- Validasi output dengan **Pydantic**. Gagal = retry 1x, lalu antrean manual.
- Antrean & jadwal: **Redis / Valkey + arq** (atau Celery bila perlu), cron per konektor.
- **Quota guard (menggantikan budget guard):** lihat §11.1. Kena 429 = job berhenti, sisa masuk antrean, diproses ulang setelah kuota reset (tengah malam waktu Pasifik). Tidak ada retry tanpa batas, tidak ada upgrade berbayar otomatis.

### 3.4 Data

- **PostgreSQL 16 + PostGIS** (wilayah & lokasi outlet) + **pgvector** (deteksi duplikat semantik).
- **Meilisearch** — typo tolerance, sinonim Bahasa Indonesia, faceting, sort. Alternatif skala besar: Typesense.
- Object storage: **penyimpanan lokal di VM (volume Docker, di dalam jatah 200 GB block storage Oracle Always Free) sebagai utama** untuk thumbnail / bukti screenshot. **Opsional:** Oracle Object Storage Always Free — 20 GB gabungan (Standard + Infrequent Access + Archive) + 50.000 request API/bulan — untuk thumbnail bila volume lokal penuh. **Cloudflare R2 DIHAPUS dari arsitektur (revisi 2).** Jangan pakai S3 berbayar.
- Cache: Redis.
- **Postgres tetap sumber kebenaran.** Google Spreadsheet adalah **cermin** saja, bukan sumber kebenaran — lihat §17.

### 3.5 Infra & kualitas — SEMUA Rp0 (revisi 2)

**Prinsip biaya: Rp0, kecuali domain (owner beli sendiri).** Tidak ada layanan yang punya jalur tagihan aktif. Semua komponen di bawah ini gratis dalam batas yang ditulis; kalau batas tercapai, layanan **berhenti / antre / drop data**, bukan menagih.

#### 3.5.1 Hosting produksi — Oracle Cloud Always Free

- **VM: Ampere A1 Flex (`VM.Standard.A1.Flex`), ARM64.** Satu VM menjalankan **seluruh** Docker Compose: Postgres+PostGIS+pgvector, Meilisearch, Redis/Valkey, API, web, worker ingest, Umami.
- **⚠️ KOREKSI PENTING — angka 4 OCPU / 24 GB tidak lagi dijamin gratis.** Dokumen resmi Oracle per Oktober–November 2026: jatah Always Free **tenancy biasa (bukan PAYG) = 1.500 OCPU-hours + 9.000 GB-hours/bulan, setara 2 OCPU + 12 GB RAM berjalan terus-menerus**. Jatah 4 OCPU / 24 GB (3.000 OCPU-hours + 18.000 GB-hours/bulan) hanya berlaku untuk **tenancy Pay As You Go (PAYG)** — akun yang sudah didaftarkan kartu dan di-upgrade ke PAYG, tapi tetap Rp0 selama tidak memakai sumber daya di luar jatah Always Free. Oracle memangkas jatah ini pada 15 Juni 2026 tanpa pengumuman publik.
  - **Keputusan desain: rancang untuk 2 OCPU / 12 GB.** Semua image harus jalan nyaman di 2 OCPU / 12 GB. Kalau owner memakai akun PAYG dan dapat 4 OCPU / 24 GB, itu bonus — bukan asumsi. **Jangan pernah** membuat sumber daya di luar jatah Always Free (VM tambahan, volume di atas 200 GB, Object Storage di atas 20 GB, egress di atas 10 TB/bulan).
  - **Risiko nyata yang harus diakui:** kapasitas A1 sering habis ("Out of host capacity") di region populer — butuh percobaan berulang / pilih region yang longgar. Oracle bisa **reclaim instance yang idle 7 hari** (CPU, network, dan memory sangat rendah) — mitigasi: cron health-check + traffic minimal berkala, jangan biarkan VM benar-benar idle. Semua resource Always Free hanya di **home region** (dipilih saat signup, tidak bisa diubah).
- **Semua image Docker wajib mendukung `linux/arm64`.** Cek di Fase 0: `postgres:16` + PostGIS, Meilisearch, Redis/Valkey, Node, Python — semua punya build arm64 resmi. Jangan pakai image yang hanya `amd64`. CI harus menjalankan `docker buildx build --platform linux/arm64` minimal untuk smoke test.
- **HTTPS otomatis: Caddy** sebagai reverse proxy di depan web + API. Caddy menerbitkan dan memperbarui sertifikat Let's Encrypt otomatis (gratis). Domain diarahkan owner sendiri (satu-satunya biaya yang diizinkan). Jangan pakai load balancer berbayar Oracle (flexible load balancer 10 Mbps memang ada di jatah free, tapi tidak dibutuhkan — Caddy di VM cukup).
- **JATAH ORACLE ALWAYS FREE LAINNYA (per dokumen Oracle, cek ulang saat deploy):**
  - Block storage: **200 GB total** (termasuk boot volume) + 5 backup volume.
  - Object Storage: **20 GB gabungan** + 50.000 request API/bulan (akun Always Free-only).
  - Egress: **10 TB/bulan**.
  - 2× VM AMD Micro (`VM.Standard.E2.1.Micro`, 1/8 OCPU, 1 GB RAM) — **tidak dipakai** untuk BuruPromo (cukup 1 VM A1), jangan nyalakan tanpa perlu.
  - 2× Autonomous Database (1 OCPU, 20 GB) — **tidak dipakai** (BuruPromo pakai Postgres di Docker).
  - Kalau ada pemakaian di atas jatah → **jangan upgrade otomatis**. Job berhenti + alert admin. Owner yang memutuskan manual.
- **JANGAN pakai Vercel Hobby** (non-komersial, tidak cocok untuk produk ini). Web jalan di VM yang sama lewat Caddy, bukan di Vercel/Cloudflare Pages.
- **Lokal vs produksi:** Docker Compose yang sama dipakai lokal dan di Oracle VM — bedanya hanya `.env` (host, domain, secret). Tidak ada Compose terpisah yang drift.

#### 3.5.2 Backup — gratis

- **Backup DB harian ke Google Drive via rclone (gratis).** Cron 02:00 WIB: `pg_dump` → kompres → `rclone copy` ke folder Google Drive owner (jatah Google Drive gratis 15 GB/akun). Retensi: 7 harian + 4 mingguan, hapus yang lama otomatis. Restore diuji di Fase 0 (satu kali restore ke DB lokal, buktikan file backup bisa dipakai — jangan klaim backup jalan tanpa pernah restore).
- Backup juga mencakup `infra/meilisearch/settings.json`, `packages/db/seed/`, dan file `.env.example` (bukan `.env` berisi secret — secret tidak pernah di-backup ke Drive).

#### 3.5.3 Monitoring — gratis

- **Sentry — Developer plan (free tier), Rp0.** Batas (per harga Sentry per Oktober 2026, cek ulang saat setup): **1 user, 5.000 error/bulan, 5 juta span/bulan, 50 session replay/bulan, 5 GB log/bulan, retensi 30 hari, 1 cron monitor, 1 uptime monitor.** Kalau kena batas: **event di-drop sampai siklus reset, tidak ditagih** — Developer plan tidak punya pay-as-you-go. Mitigasi: sampling error, jangan kirim error berulang tanpa deduplikasi, matikan replay kecuali saat error.
- **Umami — self-host di VM yang sama, Rp0.** Analitik ramah privasi, tanpa cookie pihak ketiga, data di Postgres yang sama (schema terpisah). Tidak ada batas event selain resource VM.
- **OpenTelemetry** untuk log/trace internal (ke file + Umami/Sentry, bukan ke vendor berbayar).
- Health check internal: `/admin` menampilkan status VM (CPU/RAM/disk), status tiap container, kuota Gemini hari ini, kuota Sheets per menit, dan sisa jatah Oracle (manual input dari console, bukan API berbayar).

#### 3.5.4 Tabel biaya — semua Rp0

| Komponen | Layanan | Biaya | Batas free tier | Kalau batas tercapai |
|---|---|---|---|---|
| LLM ekstraksi | Gemini 2.5 Flash-Lite, Google AI Studio, **tanpa billing account** | **Rp0** | Lihat §11.1 — bervariasi per proyek, tidak dijamin Google; bacaan 21 Okt 2026: 10 RPM / 250rb TPM / 20 RPD untuk 2.5 Flash-Lite | Job berhenti (429), sisa antre, proses ulang setelah reset tengah malam PT — **tidak ada tagihan** |
| Hosting + DB + search + cache | Oracle Always Free, VM A1 ARM | **Rp0** | 2 OCPU / 12 GB terus-menerus (tenancy biasa); 200 GB block; 20 GB Object Storage; 10 TB egress/bulan | Instance bisa direclaim kalau idle 7 hari; pemakaian di atas jatah **dilarang dibuat** — alert, bukan upgrade |
| HTTPS | Caddy + Let's Encrypt | **Rp0** | Sertifikat gratis, auto-renew | Caddy gagal renew → HTTPS mati, alert admin, perbaiki manual |
| Penyimpanan file | Volume lokal VM / Oracle Object Storage free | **Rp0** | 200 GB block / 20 GB Object Storage + 50rb req/bulan | Hapus thumbnail lama (>90 hari setelah kedaluwarsa), jangan tambah storage berbayar |
| Backup | rclone → Google Drive | **Rp0** | 15 GB Google Drive gratis/akun | Hapus backup lama (retensi 7+4), jangan beli storage |
| Spreadsheet sync | Google Sheets API, service account | **Rp0** | 300 baca/menit/proyek, 60 baca/menit/user; 300 tulis/menit/proyek, 60 tulis/menit/user; tanpa batas harian | 429 → retry backoff, antre (lihat §17). **Catatan:** Google menyebut biaya atas kuota berlebih "direncanakan" di masa depan untuk akun berbilling — karena BuruPromo **tanpa billing account**, jangan pernah hubungkan billing ke proyek ini |
| Error tracking | Sentry Developer | **Rp0** | 5.000 error/bulan, 1 user, 30 hari | Event di-drop sampai reset, tidak ditagih |
| Analitik | Umami self-host | **Rp0** | Hanya resource VM | — |
| Domain | Registrar pilihan owner | **Satu-satunya biaya, owner beli sendiri** | — | — |
| X API | — | **Rp0 (disabled)** | Tidak diaktifkan sampai Fase 2 | — |

- Semua rahasia di `.env`, sediakan `.env.example` lengkap. Tidak ada secret di client. **Tidak ada file kredensial billing di repo.**

---

## 4. Model data (inti)

Semua tabel di Drizzle (`packages/db`), migrasi versioned. Index yang tepat untuk kolom yang difilter/disortir.

### 4.1 Tabel utama

**regions** — hierarki resmi Kemendagri / BPS:
`code, name, level (provinsi/kab_kota/kecamatan), parent_code, geom (PostGIS), cluster`
Seed dari dataset kode wilayah resmi, **jangan hardcode manual**. Tabel tambahan `region_clusters` yang bisa diedit admin.

**brands** — `name, logo, kategori utama, akun sosmed resmi, website`
**merchants / outlets** — `brand_id, alamat, region_code, location (point)`
**sources** — konektor: `type (official_api|public_web|affiliate_feed|community|disabled), status, jadwal, kuota/budget, health terakhir`
**raw_items** — data mentah per tarikan (URL, teks, media, waktu ambil, hash). TTL terbatas, untuk audit & re-ekstraksi.
**promos** — tabel utama:
- `title, summary` (ditulis ulang, bukan salinan)
- `promo_type`: `persen | potongan_nominal | cashback | beli_x_gratis_y | gratis_ongkir | harga_spesial | bundling | poin | cicilan_0 | lainnya`
- `value_percent, value_amount, max_discount, min_purchase`
- `voucher_code (nullable), how_to_claim`
- `payment_methods[]`, `requirements[]` (pengguna baru, member, mahasiswa)
- `channel: online | offline | keduanya`, `platform`
- `category_ids[]`, `brand_id`
- `region_scope: nasional | provinsi | kota | outlet_tertentu` + `region_codes[]`
- `starts_at, ends_at, recurring_rule` (mis. "setiap Jumat"), `quota_note`
- `source_id, source_url, evidence_image_url`
- `confidence (0-1)`, `status: aktif | segera_berakhir | kedaluwarsa | belum_terverifikasi | dilaporkan | ditolak`
- `last_checked_at, votes_valid, votes_invalid, views, saves`
- `embedding (pgvector), dedup_key, is_seed`

**categories** — taksonomi berjenjang, disimpan di DB (bisa diubah admin), bukan hardcode di UI. Lihat §6.
**users, saved_promos, saved_searches (alert), wallet_preferences, submissions, reports, votes, moderation_log**

### 4.2 Aturan data

- Semua `*_at` disimpan UTC, ditampilkan WIB.
- `summary` ditulis ulang dalam Bahasa Indonesia natural, tanpa mengarang info yang tidak ada di sumber.
- `evidence_image_url` hanya thumbnail kecil / screenshot bukti, bukan salinan penuh konten berhak cipta.
- Jangan simpan data pribadi pemilik postingan selain handle publik & URL (UU PDP).

---

## 5. Pipeline ingestion

```
[Scheduler] → [Connector.fetch] → raw_items
  → [Normalize] (bersihkan teks, ekstrak link, unduh thumbnail kecil)
  → [OCR] (jika gambar/PDF katalog)
  → [Classifier] "apakah ini promo?" (aturan cepat + LLM kecil) → buang yang bukan
  → [Extract] LLM structured output → Pydantic validation
      (gagal = retry 1x, lalu antrean manual)
  → [Normalize tanggal] ("s.d. 30 Nov", "berlaku hari ini", "weekend ini" → datetime WIB)
  → [Geotag] (nama kota/outlet → region_code; default dari akun sumber)
  → [Categorize]
  → [Dedup] (dedup_key = brand + kode + nilai + periode;
      plus kemiripan embedding > ambang → merge, simpan semua sumber)
  → [Score confidence] (sumber resmi > akun brand > afiliasi > komunitas;
      ada tanggal jelas? ada kode? diverifikasi voting?)
  → [Upsert ke Postgres] → [Index ke Meilisearch]
  → [Sinkron Spreadsheet] (lihat §17 — setelah upsert + index berhasil)
```

Job pendukung:
- **Expire job tiap 10 menit**: ubah status berdasarkan `ends_at` (WIB), hapus dari index utama yang kedaluwarsa (tetap tersimpan untuk arsip/statistik). Definisi lihat §5.3. Promo yang kedaluwarsa **dipindah** dari sheet "Promo Aktif" ke sheet "Arsip" (lihat §17).
- **Recheck job**: promo aktif dicek ulang ke sumber dengan frekuensi sesuai jenis sumber; kalau halaman hilang/berubah → turunkan confidence.
- **Source health**: catat sukses/gagal, waktu respons, jumlah promo baru; alert ke admin kalau konektor gagal beruntun.
- **Quota guard (menggantikan budget guard):** tidak ada konektor berbayar. LLM (Gemini free tier) dan Sheets API berhenti otomatis saat kena 429 / kuota harian. LLM: lihat §11.1. Sheets: lihat §17. X: $0, disabled sampai Fase 2.
- **Web revalidate:** setiap promo baru/berubah/kedaluwarsa memicu `revalidatePath` / `revalidateTag` Next.js untuk halaman terkait (`/`, `/promo/...`, detail promo) — web update otomatis tanpa refresh manual. Lihat §17.4.

### 5.1 Interface konektor standar (WAJIB — Python Protocol / ABC)

Setiap konektor **wajib** mengimplementasikan interface ini. Tidak ada konektor yang memanggil `httpx` langsung tanpa lewat base class. Rate limit & retry ada di base, bukan di tiap konektor.

Lokasi: `services/ingest/connectors/base.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

@dataclass(frozen=True)
class RawItem:
    source_id: str            # mis. "bca", "gopay"
    source_url: str           # URL kanonis, tanpa query tracking (UTM, __cf_chl_*)
    title: str | None = None
    text: str                 # teks mentah / HTML yang sudah dibersihkan
    html: str | None = None   # HTML mentah, bila perlu re-parse
    media_urls: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None  # UTC
    content_hash: str | None = None     # sha256(text) untuk dedup mentah

@dataclass(frozen=True)
class HealthStatus:
    source_id: str
    ok: bool
    latency_ms: int | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    items_found: int = 0

class BaseConnector(ABC):
    source_id: str = ""          # mis. "bca"
    source_type: str = "public_web"  # official_api | public_web | affiliate_feed | community
    base_url: str = ""
    # Rate limit & retry bawaan — JANGAN override ke yang lebih agresif
    # tanpa persetujuan. Default: ≤1 req/detik/domain.
    # Pengecualian yang sudah diverifikasi: BNI www.bni.co.id = 1 req/5 detik,
    # hanya 14:00–22:00 UTC — tapi konektor BNI wajib pakai bniexperience,
    # bukan domain utama, jadi pengecualian ini hanya pengaman.
    rate_limit_per_second: float = 1.0
    max_retries: int = 2         # total percobaan = 1 + 2 retry, backoff eksponensial
    retry_backoff_seconds: float = 2.0
    timeout_seconds: float = 30.0
    user_agent: str = "BuruPromo/1.0 (+https://burupromo.example/about; contact: admin@burupromo.example)"

    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        """Ambil daftar item mentah dari listing/sitemap.
        WAJIB: hormati robots.txt, pakai rate limiter bawaan,
        jangan fetch URL yang di-Disallow, jangan bypass captcha/login.
        Kembalikan list kosong (bukan exception) kalau listing kosong.
        """

    @abstractmethod
    def parse(self, item: RawItem) -> RawItem:
        """Parse satu RawItem: bersihkan teks, ekstrak link/kanonis,
        normalisasi URL. TIDAK boleh memanggil LLM di sini.
        Gagal parse satu item = skip item itu + log, jangan gagalkan
        seluruh fetch().
        """

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Cek ringan: 1 request ke listing/sitemap.
        Dipakai admin + scheduler untuk kill switch otomatis
        kalau gagal beruntun.
        """

    # Disediakan base class, bukan diimplementasi ulang per konektor:
    # - fetch_with_retry(), _respect_robots(), _rate_limit(),
    #   _canonical_url(), _hash_content()
```

Aturan tambahan:
- `fetch()` hanya dari URL yang ada di `SOURCES.md` dan sudah diverifikasi. URL baru = update `SOURCES.md` dulu.
- Konektor yang butuh render JS (BCA listing, Mandiri listing, CIMB listing) wajib memakai Playwright lewat `PlaywrightFetcher` di base, bukan Selenium / bypass. Playwright hanya untuk halaman publik yang wajib render JS.
- Konektor yang di-`Disallow` di robots.txt untuk path tertentu (contoh: GoPay `/promo?page`, AZKO `/api/`, OVO `*/?*`) **dilarang** mengakses path itu. Gunakan sitemap yang diizinkan sebagai gantinya.
- Setiap konektor punya `config` di DB `sources`: `schedule`, `enabled`, `budget_daily_usd` (default 0 untuk `public_web`).

### 5.2 Skema index Meilisearch — `promos` (v1)

File settings: `infra/meilisearch/settings.json` — di-apply di Fase 0, di-version di repo. Jangan ubah settings langsung di dashboard tanpa commit.

```json
{
  "searchableAttributes": [
    "title",
    "summary",
    "brand_name",
    "voucher_code",
    "platform",
    "category_names"
  ],
  "filterableAttributes": [
    "category_ids",
    "category_slugs",
    "brand_id",
    "brand_slug",
    "platform",
    "promo_type",
    "channel",
    "payment_methods",
    "requirements",
    "region_scope",
    "region_codes",
    "cluster",
    "status",
    "is_seed",
    "ends_at",
    "starts_at",
    "value_percent",
    "value_amount",
    "min_purchase",
    "confidence",
    "has_voucher_code",
    "is_student_only"
  ],
  "sortableAttributes": [
    "ends_at",
    "starts_at",
    "created_at",
    "value_percent",
    "value_amount",
    "confidence",
    "votes_valid",
    "saves",
    "views"
  ],
  "rankingRules": [
    "words",
    "typo",
    "proximity",
    "attribute",
    "sort",
    "exactness"
  ],
  "typoTolerance": { "enabled": true, "minWordSizeForTypos": { "oneTypo": 4, "twoTypos": 8 } },
  "pagination": { "maxTotalHits": 1000 },
  "synonyms": {
    "gratis ongkir": ["free ongkir", "ongkir 0", "bebas ongkir", "freeongkir"],
    "cashback": ["kembalian", "cash back"],
    "sby": ["surabaya"],
    "bca": ["bank central asia"],
    "indomaret": ["indomart"],
    "alfamart": ["alfamart"],
    "kopi": ["coffee", "ngopi"],
    "diskon": ["discount", "disc"],
    "voucher": ["kupon", "coupon"],
    "jajan": ["snack", "camilan"]
  },
  "stopWords": ["yang", "dan", "di", "ke", "dari", "untuk", "dengan"]
}
```

Catatan:
- `searchableAttributes` sengaja **tidak** memasukkan `how_to_claim` dan `requirements[]` mentah yang panjang — yang dicari adalah judul/ringkasan/brand/kode.
- `status` hanya `aktif` dan `segera_berakhir` yang masuk index utama. `kedaluwarsa`, `ditolak`, `dilaporkan` dikeluarkan dari index utama (tetap di Postgres untuk arsip).
- `is_seed=true` **tidak pernah** di-index ke index produksi. Index dev terpisah: `promos_dev`.
- Sinonim di atas adalah daftar awal. Admin bisa edit di `/admin` → disimpan di `infra/meilisearch/settings.json` + di-apply ulang. Daftar lengkap sinonim awal ada di `packages/db/seed/synonyms.json` (Fase 0).
- Sort default di UI: relevansi. Sort lain: terbaru (`starts_at:desc`), segera berakhir (`ends_at:asc`), diskon terbesar (`value_percent:desc` lalu `value_amount:desc`), paling dipercaya (`confidence:desc` lalu `votes_valid:desc`).

Dokumen Meilisearch per promo (ringkas, bukan seluruh kolom Postgres):
`id, title, summary, brand_name, brand_slug, platform, promo_type, value_percent, value_amount, max_discount, min_purchase, voucher_code, has_voucher_code, category_ids, category_slugs, category_names, region_scope, region_codes, cluster, channel, payment_methods, requirements, is_student_only, starts_at, ends_at, status, confidence, votes_valid, saves, views, source_url, created_at`

### 5.3 Definisi expire & recurring — WAJIB sama di semua tempat

- **`segera_berakhir` = `ends_at` < 24 jam dari sekarang (WIB).**
  Status dihitung, bukan disimpan manual:
  - `now_wib >= ends_at` → `kedaluwarsa`
  - `ends_at - now_wib < 24 jam` dan `ends_at > now_wib` → `segera_berakhir`
  - selain itu dan `starts_at <= now_wib` → `aktif`
  - `starts_at > now_wib` → `belum_terverifikasi` / dijadwalkan (tidak tampil di hasil utama sampai mulai, kecuali di kalender promo Fase 3)
  - Expire job tiap 10 menit menghitung ulang status + menghapus `kedaluwarsa` dari index Meilisearch utama.
- **Promo berulang (`recurring_rule`):**
  - Format disimpan sebagai string terstruktur, contoh: `FREQ=WEEKLY;BYDAY=FR,SAT,SUN` (JSM Alfamart/Indomaret), `FREQ=WEEKLY;BYDAY=FRI`, `FREQ=MONTHLY;BYDAY=25` (payday tanggal 25), atau `FREQ=DAILY`.
  - `ends_at` untuk promo berulang adalah **akhir periode saat ini** (mis. Minggu 23:59 WIB untuk JSM minggu itu), bukan akhir selamanya.
  - Saat expire job menemukan promo berulang yang lewat `ends_at`, job **tidak menghapus promo** — job membuat **kemunculan berikutnya**: `starts_at`/`ends_at` baru dihitung dari `recurring_rule` + `recurrence_end` (bila ada), `last_checked_at` diperbarui, dan promo tetap `aktif` untuk periode berikutnya. Kalau `recurrence_end` sudah lewat atau sumber sudah tidak menampilkan pola itu saat recheck, baru ubah ke `kedaluwarsa`.
  - Contoh JSM: `recurring_rule = FREQ=WEEKLY;BYDAY=FRI,SAT,SUN`, `starts_at = Jumat 00:00 WIB`, `ends_at = Minggu 23:59 WIB`. Senin 00:00 WIB, expire job membuat kemunculan Jumat berikutnya.
  - Kalau `recurring_rule` tidak bisa diparse → `confidence` turun 0,1 dan masuk antrean manual. Jangan tebak pola.
- **TTL `raw_items` = 30 hari.**
  - `raw_items` disimpan untuk audit & re-ekstraksi, lalu dihapus otomatis setelah 30 hari (`fetched_at < now - 30 hari`).
  - Yang disimpan selamanya (di Postgres): `promos` + `moderation_log` + `sources.health`. Thumbnail bukti di penyimpanan lokal VM / Oracle Object Storage free tier disimpan selama promo masih `aktif`/`segera_berakhir` + 90 hari setelah kedaluwarsa, lalu dihapus. (Revisi 2: R2 dihapus.)
  - Job `cleanup_raw_items` jalan harian 03:00 WIB.
- **Zona waktu:** semua `*_at` disimpan UTC di DB dan Meilisearch (ISO 8601 UTC). Tampilan selalu WIB. `ends_at` yang berasal dari teks ("s.d. 30 Nov", "berlaku hari ini") dinormalisasi ke **23:59:59 WIB** di hari itu, kecuali sumber menyebut jam spesifik.

---

## 6. Taksonomi kategori (awal, di DB)

- Makanan & Minuman: kopi & minuman, makanan berat, jajanan & dessert, fast food, all-you-can-eat, delivery (GoFood/GrabFood/ShopeeFood)
- Kebutuhan Harian: minimarket (Indomaret, Alfamart, Alfamidi), grosir (Indogrosir, Lotte Grosir), supermarket, produk rumah tangga
- Fashion: pakaian, sepatu, aksesori, thrift/lokal
- Rumah & Perabot: AZKO (eks-ACE), Informa, IKEA, alat rumah
- Elektronik & Gadget
- Kecantikan & Perawatan
- E-commerce: gratis ongkir, voucher toko, flash sale, tanggal kembar
- Transportasi & Travel: ojol, tiket kereta/pesawat, hotel
- Keuangan: promo kartu kredit/debit, cashback e-wallet, cicilan 0%
- Hiburan: bioskop, streaming, game, event
- Pendidikan & Mahasiswa: diskon pelajar, kursus, software
- Pulsa, Data & Tagihan

---

## 7. Wilayah — Jawa Timur dulu

Hierarki: Provinsi → Kawasan → Kab/Kota → Kecamatan → Outlet.
Jawa Timur: 38 kab/kota (9 kota, 29 kabupaten).

### 7.1 Sumber dataset kode wilayah (WAJIB — jangan hardcode manual)

**Sumber hukum / resmi:**
- **Kepmendagri 300.2.2-2138/2025** — Keputusan Menteri Dalam Negeri tentang Kode dan Data Wilayah Administrasi Pemerintahan. Berlaku 2025-06-23. Aturan pemberian kode: **Permendagri 58/2021**. Ini sumber hukum yang dipakai bila ada sengketa kode/nama.

**Sumber siap-mesin yang dipakai untuk seed (pilih satu sebagai sumber utama, satu sebagai pembanding):**
- **Utama — Indonesia Region API (proyek independen, turunan dokumen resmi):** `https://indonesia-region.caturseptian.site/api/v1/`
  - File: `/api/v1/meta.json` (versi dataset, checksum), `/api/v1/provinces.json`, `/api/v1/regencies.json`, `/api/v1/districts.json`, `/api/v1/export/indonesia-regions.csv`
  - Dataset saat ini: `kepmendagri-300.2.2-2138-2025+2430-2025`, berlaku 2025-06-23.
  - **Bukan API resmi pemerintah** — proyek independen, Kemendagri tidak mengesahkan. Untuk keperluan hukum, rujuk PDF Kepmendagri-nya. Untuk seed, ini yang dipakai karena formatnya bersih dan berversi.
- **Pembanding — GitHub SalzBytes/wilayah_indonesia:** `https://github.com/SalzBytes/wilayah_indonesia` — relasi kode BPS + Kemendagri 2025 (BPS Semester 1 2025 + Kemendagri 2025), format MySQL `.sql`. Dipakai untuk cek silang `kode_bps` vs `kode_dagri`.
- **Alternatif — npm `idn-area-data`:** `https://github.com/fityannugroho/idn-area-data` — data wilayah dari sumber resmi terbaru, format JSON.

**Proses seed (Fase 0):**
1. Unduh CSV/JSON di atas **sekali saat build**, simpan snapshot berversi di `packages/db/seed/wilayah/kepmendagri-300.2.2-2138-2025.csv` + catat SHA-256 + tanggal unduh di `packages/db/seed/wilayah/MANIFEST.md`.
2. Jangan fetch live dari API wilayah saat runtime. Seed adalah data di repo, bukan API eksternal.
3. Simpan dua kode per wilayah bila tersedia: `code_dagri` (Kemendagri, mis. `35.78` untuk Kota Surabaya) dan `code_bps` (BPS). `code` utama di `regions.code` = `code_dagri`.
4. Verifikasi jumlah: Jawa Timur harus 38 kab/kota. Kalau jumlah tidak cocok, seed gagal dan CI gagal — jangan lanjut.

### 7.2 Sumber geometri batas wilayah

- **Badan Informasi Geospasial (BIG)** — poligon batas provinsi, kabupaten/kota, kecamatan, dan kelurahan/desa. Di Indonesia Region API, poligon BIG digabungkan dengan data Kemendagri **berdasarkan kode yang persis sama** (field BIG `KDPPUM`, `KDPKAB`, `KDCPUM`, `KDEPUM`).
- **BPS SIG — Bridging Kode:** `https://sig.bps.go.id/bridging-kode/index` — untuk pencocokan kode BPS ↔ Kemendagri.
- Penyimpanan: `regions.geom` (PostGIS `MULTIPOLYGON`, SRID 4326). Untuk Fase 0, cukup geometri tingkat provinsi + kab/kota Jawa Timur. Geometri kecamatan ditambah di Fase 3 saat fitur "promo dekat saya" butuh radius akurat.
- Kalau geometri BIG tidak bisa diunduh di Fase 0, `geom` boleh `NULL` sementara, tapi `code` + `name` + `parent_code` + `cluster` **wajib** lengkap. Catat di `MANIFEST.md` sebagai kekurangan yang diketahui, jangan pura-pura ada geometri.

Kawasan awal (verifikasi dengan data resmi, bisa diedit admin di `region_clusters`):
- **Surabaya Raya**: Kota Surabaya, Sidoarjo, Gresik (+ Bangkalan, Mojokerto, Lamongan sebagai lingkar luar / Gerbangkertosusila)
- **Malang Raya**: Kota Malang, Kab. Malang, Kota Batu
- **Madura**: Bangkalan, Sampang, Pamekasan, Sumenep
- **Tapal Kuda**: Pasuruan, Probolinggo, Lumajang, Jember, Bondowoso, Situbondo, Banyuwangi
- **Mataraman**: Madiun, Magetan, Ngawi, Ponorogo, Pacitan, Trenggalek, Tulungagung, Blitar, Kediri, Nganjuk
- **Pantura / Lainnya**: Tuban, Bojonegoro, Jombang, dll.

Aturan tampil: pengguna memilih lokasi (atau izinkan geolokasi) → hasil menampilkan **promo lokal di wilayahnya + promo provinsi + promo nasional**, dengan label jelas ("Berlaku di Surabaya", "Nasional", "Online"). Arsitektur siap tambah provinsi lain tanpa ubah kode.

---

## 8. Pencarian & personalisasi

- Pencarian instan (debounce ±120 ms), toleran typo, **sinonim Indonesia** di config Meilisearch (bisa diedit admin):
  `gratis ongkir = free ongkir = ongkir 0 = bebas ongkir`, `cashback = kembalian`, `sby = surabaya`, `bca = bank central asia`, `indomaret = indomart`, dst.
- Facet: kategori, wilayah/kawasan, platform/brand, metode bayar, tipe promo, online/offline, "berakhir hari ini", "tanpa minimal belanja", "khusus mahasiswa".
- Sort: relevansi, terbaru, segera berakhir, diskon terbesar, paling dipercaya, terdekat.
- **Dompetku** (Fase 3): pengguna memilih bank & e-wallet yang ia punya → promo yang cocok diprioritaskan & diberi tanda "Kamu bisa pakai ini".
- **Saved search + alert** (Fase 3): "kabari saya kalau ada promo kopi di Surabaya" → Web Push / Telegram bot / email digest.
- **Kalender promo** (Fase 3): tanggal kembar (11.11, 12.12), Harbolnas, payday, Ramadan, promo mingguan berulang (mis. "JSM").
- **Promo dekat saya** (Fase 3): geolokasi + PostGIS radius + peta.
- SEO: halaman statis/ISR per kombinasi penting (`/promo/makanan/surabaya`, `/promo/bank/bca`), metadata & JSON-LD, sitemap otomatis.

---

## 9. Desain UI/UX — "Label Harga & Struk Belanja"

Konsep visual: stiker harga coret di rak minimarket, struk kasir, papan pengumuman — **padat informasi, tegas, cepat dipindai**.

### Larangan keras
- Gradien ungu-biru, glassmorphism, blob/orb melayang, glow neon
- Hero besar "Temukan Promo Terbaik untuk Anda" dengan ilustrasi 3D generik
- Emoji sebagai ikon, ikon berlebihan di setiap judul
- Semua elemen `rounded-2xl` + shadow lembut seragam
- Grid kartu identik tanpa hierarki
- Teks marketing kosong ("Revolusioner", "Seamless", "Unlock")
- Animasi berlebihan yang memperlambat

### Yang harus dilakukan
- **Halaman depan = langsung search bar + hasil**, bukan hero. Di bawahnya: "Berakhir hari ini", "Promo dekat kamu", "Paling banyak disimpan", chip kategori.
- **Kartu promo seperti label harga**: angka diskon BESAR (−50%, Rp15rb, GRATIS ONGKIR) sebagai fokus, logo brand kecil + nama, badge wilayah, badge sumber (ikon platform monokrom), kode voucher dalam kotak bergaris putus-putus + tombol salin "Tersalin", hitung mundur ("Berakhir 3 jam lagi") dengan warna urgensi, indikator kepercayaan ("Dari akun resmi" / "Kiriman komunitas · 12 orang bilang masih berlaku").
- **Dua mode tampilan**: Kartu dan Daftar padat (seperti tabel struk).
- **Halaman detail**: syarat lengkap dalam bentuk checklist, metode pembayaran, daftar outlet + peta mini, link "Lihat di sumber", tombol "Masih berlaku?", laporkan, simpan, bagikan.

### Design tokens (titik awal)
- Terang: kertas `#F6F3EC`, tinta `#151515`, garis `#D9D3C7`, merah stiker `#E4572E`, kuning label `#FFD23F`, hijau valid `#1F7A4C`, abu sekunder `#6B665E`
- Gelap: latar `#121110`, permukaan `#1C1B19`, teks `#EDE8DE`, aksen sama dengan kontras disesuaikan
- Tipografi: judul/angka besar **Bricolage Grotesque**, teks **Schibsted Grotesk / Inter Tight**, kode & angka **JetBrains Mono** (tabular numbers)
- Skala spasi 4px, radius kecil (4–8px) kecuali chip, bayangan minim — gunakan garis & kontras, bukan blur
- Kontras minimal **WCAG AA**, area sentuh ≥ 44px, navigasi keyboard lengkap

### Mobile-first
- Bottom navigation: Cari · Dekat · Disimpan · Notifikasi · Akun
- Filter dalam bottom sheet, sticky search bar, infinite scroll dengan skeleton yang meniru bentuk kartu.

---

## 10. Komunitas & moderasi

- Form kirim promo (link + foto opsional) dengan **Cloudflare Turnstile** anti-spam, rate limit per pengguna.
- **PWA Share Target**: dari IG/X/TikTok → Bagikan → BuruPromo → otomatis diekstrak → masuk antrean moderasi. Ini cara legal & kuat untuk menangkap promo dari aplikasi tertutup.
- Voting validitas, laporan ("kode tidak bisa", "kuota habis", "palsu/penipuan").
- Reputasi pengguna: kiriman yang terbukti benar menaikkan skor; spam menurunkan.
- **Deteksi penipuan**: tandai pola link phishing, domain mencurigakan, permintaan transfer/OTP → tolak otomatis.
- Moderation log: siapa mengubah apa, kapan.

## Admin panel (`/admin`)

- Dashboard: promo baru per sumber, promo aktif, kedaluwarsa hari ini, **kuota LLM hari ini (dipakai / sisa / reset) + status antrean**, kuota Sheets per menit, status sinkron Spreadsheet terakhir (lihat §17), status VM Oracle.
- Source health: status tiap konektor, error terakhir, tombol jalankan ulang, kill switch.
- Antrean review: promo confidence rendah & kiriman komunitas → setujui/edit/tolak sekali klik, tampilkan bukti asli di samping hasil ekstraksi.
- Kelola brand, outlet, kategori, wilayah, sinonim, akun IG/hashtag yang dipantau (dengan penghitung kuota 30 hashtag/7 hari).
- Log moderasi.

---

## 11. Keputusan owner — REVISI 2, DIPUTUSKAN 2026-11-22 (menggantikan revisi 1)

**Prinsip: SEMUA GRATIS (Rp0), kecuali domain yang owner beli sendiri.**

| # | Keputusan | Keputusan owner (revisi 2) | Detail / guard |
|---|---|---|---|
| 1 | **Provider LLM untuk ekstraksi** | **Gemini API FREE TIER saja via Google AI Studio, TANPA billing account.** Model: Gemini 2.5 Flash-Lite (`gemini-2.5-flash-lite`). **Budget $5/bulan DIHAPUS.** | Lihat §11.1 (quota guard). Tidak ada fallback berbayar. Fallback bila kuota habis = ekstraksi berbasis aturan + antrean manual. |
| 2 | **Hosting produksi** | **Oracle Cloud Always Free — VM ARM Ampere A1, seluruh Docker Compose di satu VM + Caddy untuk HTTPS otomatis.** | Lihat §3.5.1. Rancang untuk **2 OCPU / 12 GB** (tenancy biasa); 4 OCPU / 24 GB hanya bila akun PAYG. Semua image wajib `linux/arm64`. **JANGAN pakai Vercel Hobby.** |
| 3 | **Penyimpanan file** | **Lokal di VM (volume Docker) sebagai utama; opsional Oracle Object Storage free tier.** | R2 dihapus. Batas: 200 GB block / 20 GB Object Storage + 50rb req/bulan. |
| 4 | **Backup** | **Rclone → Google Drive, harian, gratis.** | Cron 02:00 WIB, retensi 7 harian + 4 mingguan, restore diuji sekali di Fase 0. |
| 5 | **Monitoring** | **Sentry free tier (Developer) + Umami self-host di VM yang sama.** | Sentry: 5.000 error/bulan, 1 user, 30 hari — event di-drop bila habis, tidak ditagih. Umami: tanpa batas selain resource VM. |
| 6 | **Sinkron Spreadsheet** | **Google Sheets API via service account, gratis. Postgres tetap sumber kebenaran, Spreadsheet = cermin.** | Lihat §17. Batch update, upsert by `id`, retry backoff. |
| 7 | **X API** | **Budget $0. Tidak diaktifkan sampai Fase 2.** | Konektor X berstatus `disabled` di `sources` + di `/admin`. Jangan daftar API X berbayar sebelum Fase 2 dan persetujuan ulang. |
| 8 | App Review Instagram / Threads | Ajukan setelah Fase 1 stabil. Fase awal: Business Discovery akun yang dikurasi + mode terbatas Threads. | Cakupan data sosial terbatas di awal |
| 9 | Monetisasi afiliasi | Fase 4. Fase 1–3 fokus ke akurasi & kepercayaan. | Legalitas Reddit komersial, dll. |

### 11.1 LLM free tier — quota guard (menggantikan budget guard)

**Aturan keras: proyek Google Cloud untuk BuruPromo TIDAK BOLEH punya billing account.** Tanpa billing account, tidak ada jalur yang bisa menimbulkan tagihan — API yang melebihi free tier hanya mengembalikan 429, bukan menagih. **Jangan pernah** menghubungkan kartu / billing ke proyek ini, dan jangan pernah meminta peningkatan kuota yang butuh billing.

**Batas free tier — jujur, tidak dijamin Google:**
- Google tidak lagi memublikasikan tabel batas yang dijamin; halaman Rate Limits resmi mengarahkan ke AI Studio dan menyebut batas "tidak dijamin" dan "bervariasi per proyek". Artinya: **angka di bawah ini adalah bacaan dari satu proyek, bukan janji.**
- Bacaan AI Studio **21 Oktober 2026** (sumber sekunder yang membaca halaman AI Studio langsung): **Gemini 2.5 Flash-Lite = 10 RPM / 250.000 TPM / 20 RPD.** Model Flash-Lite yang lebih baru (Gemini 3.5 / 3.1 Flash-Lite) pada bacaan yang sama: 15 RPM / 500 RPD. Bacaan lain yang lebih lama menyebut 15 RPM / 1.000 RPD untuk 2.5 Flash-Lite — **jangan pakai angka lama itu sebagai asumsi.** RPD 20/hari adalah skenario terburuk yang harus ditahan desain.
- **Reset: tengah malam waktu Pasifik (00:00 PT).** Kuota dihitung per proyek Google Cloud, bukan per API key — kunci kedua tidak menambah kuota.
- **Verifikasi wajib saat implementasi:** buka AI Studio → Rate Limits di proyek owner sendiri, catat RPM / TPM / RPD yang tampil di sana ke `docs/adr/` + `/admin`, dan sesuaikan `LLM_DAILY_BUDGET` (dalam jumlah request, bukan rupiah) dengan angka itu. Jangan hardcode 1.000/hari.

**Quota guard — perilaku saat kena batas:**
1. Kena **429** (RPM, TPM, atau RPD) → job **berhenti segera**, tidak retry membabi buta. Retry hanya dengan backoff eksponensial (2 dtk, 4 dtk, 8 dtk, maks 3x) untuk 429 sesaat (RPM). Untuk RPD habis, **tidak ada retry hari itu**.
2. Sisa item masuk antrean `llm_queue` di Redis/Postgres dengan status `menunggu_kuota`, diproses ulang **setelah reset tengah malam PT** (job scheduler cek kuota dulu sebelum mulai).
3. Selama kuota habis, pipeline tetap jalan dengan **ekstraksi berbasis aturan** (regex tanggal/nilai/kode + classifier aturan) dan confidence diturunkan 0,1 + masuk antrean review manual bila field wajib kosong. Promo **tidak boleh** dibuat dengan field yang ditebak LLM tanpa bukti.
4. Admin melihat di `/admin`: dipakai hari ini / sisa / reset berikutnya / jumlah antrean. Alert saat antrean > 50 item.
5. **Tidak ada jalur upgrade berbayar di kode.** Tidak ada tombol "naikkan kuota", tidak ada fallback ke model berbayar, tidak ada fallback ke provider berbayar (OpenAI dihapus sebagai fallback — interface LLM tetap bisa diganti, tapi penggantinya harus free tier lain yang disetujui owner dulu).

**Hemat kuota (desain, bukan anjuran):** aturan dulu → LLM hanya untuk yang ambigu; batch beberapa promo per call; cache per `content_hash`; jangan panggil LLM untuk klasifikasi bila aturan sudah menjawab. Dengan RPD 20/hari, **20 promo/hari adalah batas keras ekstraksi LLM** — Fase 1 menargetkan ≥ 200 promo aktif, jadi sebagian besar promo harus lolos lewat aturan + review manual, bukan LLM. Itu konsekuensi yang harus diterima dari keputusan Rp0, dan harus jujur dilaporkan ke owner bila target Fase 1 tidak tercapai karena kuota.

---

## 12. Non-fungsional

- **Performa**: LCP < 1,8 dtk di 4G HP menengah, JS awal < 150 KB gzip, respons search p95 < 150 ms, Lighthouse ≥ 95 (Fase 1 minimal ≥ 90).
- **Kesegaran data**: promo sumber resmi dicek ulang minimal tiap 6 jam; promo "segera berakhir" < 24 jam.
- **Keamanan**: CSP ketat, rate limit API, sanitasi semua HTML dari sumber luar, tidak ada secret di client, dependensi diaudit di CI.
- **Testing**: unit test parser tiap konektor (pakai **fixture HTML/JSON yang disimpan**, bukan request live), test ekstraksi LLM dengan golden set ≥ 30 promo nyata yang dianotasi, e2e alur utama.
- **Zona waktu**: simpan UTC, tampil WIB.

### 12.1 Fixture test WAJIB untuk setiap konektor sejak Fase 1

Bukan anjuran — **syarat merge**.

- Lokasi: `services/ingest/connectors/tests/fixtures/<source_id>/`
  - `listing.html` (atau `listing.json` / `sitemap.xml` — sesuai tipe sumber)
  - Minimal 2 `detail-1.html`, `detail-2.html`
  - `expected.json` — hasil parse + ekstraksi yang diharapkan untuk fixture itu (judul, nilai, tanggal WIB, kode, region)
- Test: `services/ingest/connectors/tests/test_<source_id>.py` — `pytest` menjalankan `fetch` **dari fixture lokal** (mock HTTP), lalu `parse()` + pipeline normalize/dedup/score. **Tidak ada request live di test.**
- Fixture diambil dari halaman publik yang sudah diverifikasi di `SOURCES.md` (disimpan sebagai file, bukan disalin utuh ke produksi — hanya untuk test, dengan atribusi URL sumber di header file).
- Konektor baru tanpa fixture + test hijau **tidak boleh merge**. CI gagal kalau ada konektor tanpa fixture.
- Golden set LLM: ≥ 30 promo nyata yang dianotasi (judul, nilai, tanggal, syarat) di `services/ingest/pipeline/tests/golden/`. Ekstraksi LLM harus lolos ≥ 90% field wajib benar sebelum Fase 1 dinyatakan selesai.

---

## 13. Rencana Fase 0 — yang dikerjakan sekarang

### Scope Fase 0
- [ ] Monorepo Turborepo + pnpm, uv untuk Python
- [ ] Docker Compose: postgres+PostGIS+pgvector, redis/valkey, meilisearch, api, web, ingest + **Caddy** (HTTPS otomatis). **Semua image wajib `linux/arm64`** — cek `docker buildx build --platform linux/arm64` di CI.
- [ ] DB schema + migrasi Drizzle, seed wilayah Jawa Timur dari data resmi (Kepmendagri 300.2.2-2138/2025, lihat §7.1) + `MANIFEST.md` + SHA-256
- [ ] Meilisearch settings: sinonim Indonesia, typo tolerance, faceting, sort (skema di §5.2, file `infra/meilisearch/settings.json`)
- [ ] Design tokens + komponen dasar (`packages/ui`)
- [ ] Interface konektor standar `BaseConnector` (§5.1) + rate limit & retry bawaan
- [ ] Kontrak OpenAPI `/v1` (lihat §16) + Zod di `packages/contracts`
- [ ] **Quota guard LLM (§11.1) + antrean `llm_queue`** — tanpa billing account, tanpa jalur berbayar
- [ ] **Sinkron Spreadsheet — kerangka (§17):** modul `services/ingest/sync/sheets.py` + tabel `sync_log` + 3 sheet (Promo Aktif / Arsip / Log Sinkron) + batch update + retry backoff. Isi penuh di vertical slice BCA.
- [ ] **Backup harian:** skrip `infra/backup/backup.sh` (pg_dump → rclone → Google Drive) + cron 02:00 WIB + **satu kali uji restore** ke DB lokal
- [ ] **Monitoring gratis:** Sentry Developer (DSN di `.env`) + Umami self-host di Compose yang sama
- [ ] CI GitHub Actions: Biome, Ruff, typecheck, test — termasuk **cek fixture wajib**: CI gagal kalau ada konektor tanpa fixture
- [ ] `docs/ARCHITECTURE.md` (file ini, revisi 2) + `docs/SOURCES.md` (revisi 1, terverifikasi)

### Kriteria selesai Fase 0
- `docker compose up` menyalakan semua layanan
- Halaman web tampil dengan design system (bukan hero generik)
- CI hijau
- Seed wilayah Jawa Timur = 38 kab/kota, lengkap dengan `code_dagri`

### Yang TIDAK dikerjakan di Fase 0
- Tidak ada konektor produksi yang diaktifkan sebelum SOURCES.md disetujui — **SOURCES.md revisi 1 sudah disetujui, jadi Fase 0 boleh lanjut**
- Tidak ada data promo palsu di produksi (`is_seed=true` hanya di dev, tidak di-index produksi)
- Tidak ada pendaftaran API berbayar, tidak ada billing account di proyek Google Cloud mana pun, tidak ada sumber daya Oracle di luar jatah Always Free (LLM Gemini free tier dengan quota guard §11.1, X budget $0/disabled)
- Tidak ada deploy berbayar (lokal dulu untuk dev; produksi di Oracle Always Free, Rp0 — deploy produksi bukan bagian Fase 0, dilakukan setelah Fase 0 + vertical slice BCA selesai dan owner setuju)
- **JANGAN pakai Vercel Hobby, jangan pakai Cloudflare R2**

### Setelah Fase 0 — VERTICAL SLICE dulu (keputusan owner)

**Jangan langsung tambah semua sumber Fase 1. Kerjakan dulu 1 konektor end-to-end: BCA.**

Urutan vertical slice BCA:
1. `bank_bca.py` mengimplementasikan `BaseConnector` (§5.1) + fixture (`listing.html` dari sitemap `promo.bca.co.id/sitemap.xml` + 2 detail) + test hijau.
2. Pipeline lengkap untuk BCA: fetch → normalize → classifier → extract LLM (Gemini 2.5 Flash-Lite free tier, quota guard §11.1 — aturan dulu, LLM hanya untuk yang ambigu) → normalize tanggal WIB → geotag → categorize → dedup → score → upsert Postgres → index Meilisearch → **sinkron Spreadsheet (§17)** → revalidate web.
3. API `GET /v1/promos` + `GET /v1/promos/:id` menampilkan promo BCA.
4. Web menampilkan promo BCA dengan design system Label Harga & Struk Belanja (kartu + detail + tombol salin kode + hitung mundur + badge sumber).
5. Admin bisa lihat source health BCA + kill switch.

**Kriteria vertical slice selesai:** minimal 1 promo BCA nyata (bukan dummy) tampil end-to-end di web lokal, dari fetch sampai tampil, dengan link sumber yang benar dan `ends_at` WIB yang benar. Baru setelah itu tambah sumber lain (urutan: GoPay → DANA → BNI via bniexperience → AZKO → Informa → CIMB → Mandiri → BRI → Indomaret via Klik Indomaret). Alfamart & Alfamidi tetap `disabled` sampai ada jalur legal yang terverifikasi.

---

## 14. Fase berikutnya (ringkas)

- **Fase 1 — MVP Surabaya**: 5 bank (BCA, Mandiri, BRI, BNI via bniexperience, CIMB Niaga), Indomaret (via Klik Indomaret + katalog, bukan listing indomaret.co.id), AZKO, Informa, 3 e-wallet (GoPay, OVO, DANA), + komunitas & Share Target. **Alfamart & Alfamidi: `disabled` di Fase 1** (Alfamart: reCAPTCHA/bot wall; Alfamidi: tidak ada URL resmi terverifikasi — lihat SOURCES.md revisi 1). Alfagift tetap jadi alternatif untuk Alfamart. Pipeline lengkap, pencarian + filter + detail, simpan promo, admin review. Selesai jika ≥ 200 promo aktif nyata terindeks, tidak ada promo kedaluwarsa tampil sebagai aktif, Lighthouse ≥ 90. **Urutan bangun: vertical slice BCA dulu, baru GoPay → DANA → BNI → AZKO → Informa → CIMB → Mandiri → BRI → Indomaret.**
- **Fase 2 — Media sosial via API resmi**: Instagram Business Discovery + Hashtag Search (setelah App Review), Threads keyword search, X recent search dengan budget cap, Reddit (non-komersial). Selesai jika tiap konektor punya fixture test, budget guard terbukti menghentikan job, admin bisa mematikan konektor.
- **Fase 3 — Personalisasi & notifikasi**: Dompetku, saved search + Web Push/Telegram, promo dekat saya + peta, kalender promo, halaman SEO.
- **Fase 4 — Skala**: Provinsi lain, afiliasi e-commerce sebagai sumber + monetisasi, worker Go bila perlu, caching edge.

---

## 15. Risiko utama

1. **Sumber berubah / diblokir** → mitigasi: konektor terisolasi, kill switch, health check, fallback ke komunitas + akun resmi.
2. **Kuota LLM free tier habis (RPD sangat kecil, bisa 20/hari)** → mitigasi: quota guard §11.1, aturan dulu, batch, cache, antrean + proses ulang setelah reset PT, review manual. Konsekuensi jujur: target ≥ 200 promo Fase 1 bisa melambat bila kuota jadi bottleneck.
3. **Oracle Always Free: kapasitas A1 habis / instance direclaim saat idle 7 hari / jatah ternyata 2 OCPU bukan 4** → mitigasi: rancang untuk 2 OCPU / 12 GB, cron health-check agar tidak idle, pilih region longgar, jangan buat resource di luar jatah, alert admin. Kalau A1 tidak didapat, Fase 0 tetap jalan lokal; deploy produksi ditunda sampai VM didapat — jangan paksa pakai VPS berbayar tanpa persetujuan owner.
4. **Kuota Sheets API habis (429)** → mitigasi: batch update, retry backoff §17, antrean sinkron. Spreadsheet ketinggalan tidak boleh memblokir Postgres/Meilisearch/web — sync adalah cermin, bukan jalur kritis.
5. **Data kedaluwarsa / salah** → mitigasi: expire job 10 menit, recheck, voting, confidence score, moderasi.
6. **Katalog berupa gambar/PDF** → mitigasi: OCR + LLM ekstraksi, antrean manual untuk yang gagal.
7. **Penipuan / phishing dari kiriman komunitas** → mitigasi: Turnstile, deteksi domain mencurigakan, moderasi, reputasi.
8. **Legalitas Reddit komersial** → mitigasi: mulai non-komersial, matikan atau urus lisensi sebelum monetisasi.
9. **Google mengubah aturan Sheets API (biaya atas kuota berlebih "direncanakan")** → mitigasi: proyek **tanpa billing account**, jadi tidak ada yang bisa ditagih; kalau Google suatu hari mewajibkan billing untuk Sheets API, sinkron Spreadsheet dimatikan (kill switch) dan Postgres tetap jalan — jangan hubungkan billing tanpa persetujuan owner.

---

## 16. Kontrak OpenAPI `/v1` (ringkas — sumber kebenaran di `packages/contracts` + `apps/api/openapi.yaml`)

Base: `/v1`. Auth: Better Auth, header `Authorization: Bearer <token>` untuk endpoint yang butuh login. Rate limit: 60 req/menit/IP untuk publik, 300 req/menit untuk user login. Semua waktu ISO 8601 UTC, tampil WIB di client. Error standar: `{ "error": { "code": "NOT_FOUND", "message": "..." } }`.

### 16.1 Promo — publik

**`GET /v1/promos`**
- Query: `q` (string), `category` (slug, bisa banyak, koma), `region` (kode Kemendagri, mis. `35.78` Surabaya, atau `nasional`), `cluster` (mis. `surabaya-raya`), `brand` (slug), `platform`, `promo_type`, `channel` (`online|offline|keduanya`), `payment` (mis. `bca`, `gopay`), `ends_today` (bool), `ends_soon` (bool, <24 jam), `no_min_purchase` (bool), `student_only` (bool), `sort` (`relevance|newest|ending_soon|biggest_discount|most_trusted|nearest`), `lat`, `lon`, `radius_km` (Fase 3), `page` (default 1), `per_page` (default 20, maks 50)
- Response 200: `{ "data": [PromoSummary], "meta": { "page": 1, "per_page": 20, "total": 123, "total_pages": 7 } }`
- `PromoSummary`: `{ "id": "uuid", "title": "string", "summary": "string", "brand": { "id": "uuid", "name": "BCA", "slug": "bca", "logo_url": "…" }, "platform": "BCA", "promo_type": "persen", "value_percent": 50, "value_amount": null, "max_discount": 150000, "min_purchase": 0, "voucher_code": "…|null", "channel": "online", "category_slugs": ["makanan-minuman"], "region_scope": "nasional", "region_codes": [], "starts_at": "2026-11-01T00:00:00Z", "ends_at": "2026-11-30T16:59:59Z", "status": "aktif|segera_berakhir", "confidence": 0.92, "votes_valid": 12, "votes_invalid": 1, "saves": 45, "source_url": "https://promo.bca.co.id/…", "evidence_image_url": "…|null" }`

**`GET /v1/promos/{id}`**
- Response 200: `PromoDetail` = `PromoSummary` + `{ "how_to_claim": "…", "requirements": ["…"], "payment_methods": ["bca"], "outlets": [{ "id": "uuid", "name": "…", "address": "…", "region_code": "35.78", "lat": -7.25, "lon": 112.75 }], "source": { "id": "uuid", "name": "BCA", "type": "public_web" }, "last_checked_at": "…" }`
- 404 kalau id tidak ada atau status `ditolak`/`kedaluwarsa` (tetap 404, bukan tampil sebagai aktif).

**`POST /v1/promos/{id}/vote`** — butuh login
- Body: `{ "vote": "valid"|"invalid" }` — satu user satu vote per promo, bisa ubah vote.
- Response 200: `{ "votes_valid": 13, "votes_invalid": 1 }`

**`POST /v1/promos/{id}/report`** — butuh login
- Body: `{ "reason": "kode_tidak_bisa"|"kuota_habis"|"palsu"|"lainnya", "note": "string, opsional, maks 500 karakter" }`
- Response 201: `{ "id": "uuid", "status": "dilaporkan" }` — promo tidak langsung hilang, masuk antrean moderasi.

### 16.2 Simpan, alert, dompet — butuh login

- **`GET /v1/saved-promos`** — list promo yang disimpan user. **`POST /v1/saved-promos`** body `{ "promo_id": "uuid" }`. **`DELETE /v1/saved-promos/{promo_id}`**
- **`GET /v1/saved-searches`** — **`POST /v1/saved-searches`** body `{ "query": "kopi", "category": "makanan-minuman", "region": "35.78", "notify_via": ["push","telegram","email"] }` (Fase 3). **`DELETE /v1/saved-searches/{id}`**
- **`GET /v1/wallet`** — **`PUT /v1/wallet`** body `{ "banks": ["bca","mandiri"], "ewallets": ["gopay","ovo","dana"] }` (Fase 3, Dompetku)

### 16.3 Kiriman komunitas — publik + login

- **`POST /v1/submissions`** — butuh login + Turnstile. Body: `{ "source_url": "https://…", "title": "string, opsional", "note": "string, opsional", "photo_url": "…|null" }`. Response 201: `{ "id": "uuid", "status": "menunggu_moderasi" }`. Rate limit: 5/hari/user.
- **`GET /v1/submissions/me`** — list kiriman sendiri + statusnya.

### 16.4 Referensi — publik

- **`GET /v1/regions?level=provinsi|kab_kota|kecamatan&parent=35`** — hierarki Kemendagri. **`GET /v1/regions/{code}`**
- **`GET /v1/categories`** — taksonomi dari DB. **`GET /v1/brands?category=…`**
- **`GET /v1/sources`** — daftar konektor + `status` + `last_success_at` (tanpa secret/budget detail).

### 16.5 Admin — peran `admin` / `moderator` saja

- **`GET /admin/stats`** — promo baru per sumber, aktif, kedaluwarsa hari ini, **kuota LLM hari ini (dipakai / sisa / reset PT) + antrean `llm_queue`**, status sinkron Spreadsheet terakhir, kuota Sheets per menit.
- **`GET /admin/sources`** — **`POST /admin/sources/{id}/toggle`** body `{ "enabled": false }` (kill switch), **`POST /admin/sources/{id}/rerun`**
- **`GET /admin/review-queue`** — **`POST /admin/review-queue/{id}/approve|reject`** body `{ "note": "…" }` — tampilkan bukti asli di samping hasil ekstraksi.
- **`GET /admin/moderation-log`**

Semua endpoint admin mengembalikan 403 kalau peran tidak cukup. Kontrak lengkap (Zod + OpenAPI YAML) dibuat di Fase 0 di `packages/contracts` dan `apps/api/openapi.yaml` — dokumen ini ringkasannya, bukan pengganti file itu.

---

## 17. Sinkron Google Spreadsheet — cermin otomatis (BARU, revisi 2)

**Prinsip: Postgres tetap sumber kebenaran. Spreadsheet = cermin otomatis, bukan sumber kebenaran.** Kalau Spreadsheet ketinggalan, rusak, atau API-nya mati, web + Postgres + Meilisearch tetap jalan. Jangan pernah membaca promo dari Spreadsheet untuk ditampilkan di web. Jangan pernah menulis ke Postgres dari Spreadsheet tanpa moderasi manual.

### 17.1 Kapan sinkron terjadi

Setiap kali promo **dibuat / diubah / kedaluwarsa**, setelah upsert ke Postgres **dan** index ke Meilisearch berhasil, worker langsung memicu sinkron Spreadsheet. Urutan wajib:
`upsert Postgres → index Meilisearch → sinkron Sheets → revalidate web (§17.4)`.
Kalau langkah Sheets gagal, Postgres + Meilisearch **tidak di-rollback** — kegagalan Sheets dicatat di `sync_log` + antrean retry, dan promo tetap tampil di web.

Pemicu lain: vote/report yang mengubah `status` (mis. `dilaporkan` → `ditolak`), perubahan manual dari `/admin`, dan expire job tiap 10 menit (yang kedaluwarsa pindah sheet).

### 17.2 Struktur spreadsheet

Satu spreadsheet (ID di `.env`: `GOOGLE_SHEETS_SPREADSHEET_ID`), dibuat sekali secara manual oleh owner (atau skrip setup Fase 0 yang meminta owner share spreadsheet ke service account). Tiga sheet:

**Sheet 1 — "Promo Aktif"** (hanya `status = aktif` atau `segera_berakhir`)
Kolom (baris 1 = header, jangan diubah urutannya tanpa migrasi):
`id | judul | brand | kategori | nilai_diskon | kode | metode_bayar | wilayah | mulai | berakhir_WIB | status | sumber_URL | terakhir_dicek`
- `id`: UUID Postgres (kunci upsert — lihat §17.3).
- `nilai_diskon`: teks yang tampil, mis. `50%`, `Rp15.000`, `Gratis ongkir`, `Cashback 10%`.
- `kategori`: dipisah koma, mis. `Makanan & Minuman, Kopi`.
- `metode_bayar`: dipisah koma, mis. `BCA, GoPay`.
- `wilayah`: mis. `Surabaya`, `Nasional`, `Jawa Timur`.
- `mulai` / `berakhir_WIB`: format `YYYY-MM-DD HH:mm WIB` (teks, bukan serial date Sheets — supaya tidak berubah zona waktu saat dibuka di HP).
- `terakhir_dicek`: `YYYY-MM-DD HH:mm WIB` dari `last_checked_at`.

**Sheet 2 — "Arsip"** (hanya `status = kedaluwarsa` / `ditolak`)
Kolom sama persis dengan "Promo Aktif", ditambah kolom terakhir `alasan_arsip` (`kedaluwarsa` / `ditolak` / `dilaporkan`).

**Sheet 3 — "Log Sinkron"** (audit, append-only)
Kolom: `waktu_WIB | promo_id | aksi | status | detail`
- `aksi`: `upsert` / `pindah_arsip` / `hapus` / `retry` / `gagal`.
- `status`: `ok` / `gagal` / `antre`.
- `detail`: pesan error singkat (tanpa secret), mis. `429 Sheets API, retry 60 dtk`.

Jangan simpan data pribadi di sheet mana pun selain yang sudah ada di `promos` (UU PDP — sama seperti §4.2).

### 17.3 Upsert berdasarkan `id` — jangan duplikat baris

- **Kunci: kolom `id`.** Sebelum tulis, worker membaca kolom `id` di sheet target (cache di Redis 5 menit, jangan baca sheet tiap promo — hemat kuota). Kalau `id` sudah ada → **update baris itu** (bukan tambah baris baru). Kalau belum ada → append baris baru.
- **Batch update untuk hemat kuota:** jangan 1 promo = 1 request. Kumpulkan perubahan dalam jendela 30 detik (atau sampai 50 baris), lalu kirim **satu** `spreadsheets.values.batchUpdate` per sheet. Satu batch = 1 write request, bukan 50.
- **Pindah ke Arsip:** saat promo kedaluwarsa, worker (1) hapus baris dari "Promo Aktif" (via `batchUpdate` dengan range yang sudah diketahui dari cache `id → row`), (2) append ke "Arsip". Dua langkah ini dalam satu batch bila memungkinkan; kalau langkah (1) gagal, jangan lakukan (2) dua kali — cek `id` di "Arsip" dulu sebelum append.
- **Idempotensi:** menjalankan sinkron yang sama dua kali tidak boleh membuat baris ganda. Selalu cek `id` dulu.

### 17.4 Web update otomatis

Saat promo baru masuk / berubah / kedaluwarsa, setelah langkah Sheets (atau bersamaan, jangan tunggu Sheets bila Sheets antre):
- API memanggil `revalidatePath("/")`, `revalidatePath("/promo/...")`, `revalidatePath("/promo/[id]")` dan `revalidateTag("promos")` di Next.js — halaman terkait di-render ulang di server, pengguna tidak perlu refresh manual.
- Kalau Sheets sedang antre/retry, **revalidate tetap jalan** — web tidak boleh menunggu Spreadsheet.

### 17.5 Kuota, retry, dan kalau batas tercapai

- **Auth:** service account Google (JSON key di `.env` / secret manager lokal, **bukan** di repo). Spreadsheet di-share ke email service account sebagai Editor. Service account **tidak punya billing account** — proyek Google Cloud-nya sama dengan proyek Gemini: tanpa billing.
- **Batas Sheets API (per dokumen Google, cek ulang saat setup):** baca 300/menit/proyek + 60/menit/user; tulis 300/menit/proyek + 60/menit/user; tanpa batas harian selama dalam batas per menit. **Service account dihitung sebagai satu user, jadi batas 60/menit/user adalah yang mengikat** — bukan 300. Desain batch di §17.3 dibuat untuk angka 60 ini.
- **Retry dengan backoff:** kena 429 → tunggu 2 dtk, 4 dtk, 8 dtk, 16 dtk, 32 dtk (maks 5x, dengan jitter). Setelah itu, masuk antrean `sheets_queue` di Redis, diproses ulang 1 menit kemudian. Catat ke "Log Sinkron" dengan status `antre` / `gagal`.
- **Kalau batas tercapai terus:** sinkron tertunda, bukan gagal permanen. Admin melihat di `/admin`: antrean Sheets, error terakhir, waktu sinkron terakhir yang sukses. **Kill switch:** `/admin` → matikan sinkron Spreadsheet kapan saja; Postgres + web tetap jalan.
- **Catatan biaya masa depan:** halaman batas Google menyebut biaya atas kuota berlebih "direncanakan" untuk akun berbilling di masa depan. Karena proyek ini **tanpa billing account**, tidak ada yang bisa ditagih — tapi kalau Google suatu hari mewajibkan billing untuk Sheets API, sinkron dimatikan (lihat risiko §15.9), jangan hubungkan billing tanpa persetujuan owner.
- **Tabel `sync_log` di Postgres:** `id, promo_id, sheet, action, status, error, attempted_at, completed_at` — sumber kebenaran untuk audit sinkron, cermin dari sheet "Log Sinkron".

### 17.6 Yang TIDAK dilakukan Spreadsheet

- Bukan backup (backup tetap rclone → Google Drive, lihat §3.5.2).
- Bukan tempat edit promo — edit hanya di `/admin` atau pipeline; edit manual di Spreadsheet **akan ditimpa** sinkron berikutnya (dan itu disengaja, supaya tidak ada dua sumber kebenaran).
- Bukan tempat simpan secret / API key / data pribadi.

---

*Dokumen ini adalah revisi 2 Fase 0 — SEMUA GRATIS (Rp0). Perubahan arsitektur dicatat sebagai ADR di `docs/adr/`.*
