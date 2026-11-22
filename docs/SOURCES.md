# SOURCES.md — Katalog Sumber BuruPromo

> Status: **REVISI 1 — disetujui owner dengan revisi, diverifikasi 2026-11-22**
> Tanggal verifikasi: 2026-11-22 (browser.open + browser.search, halaman publik)
> Prinsip: utamakan API resmi & feed afiliasi. Scraping hanya halaman publik tanpa login, hormati `robots.txt`, rate limit sopan (≤1 req/detik/domain, kecuali ada aturan lebih ketat di robots.txt — contoh BNI 1 req/5 detik), User-Agent jujur, cache.
> Dilarang: bypass login, bypass captcha/anti-bot, akun palsu, mencuri cookie/session, menyalin konten berhak cipta secara utuh.
> Catatan: kondisi API bisa berubah. **Cek ulang saat implementasi.** Kalau sebuah sumber ternyata butuh login/captcha/melanggar ToS, tandai `disabled` dengan alasannya, jangan dipaksa.

Status konektor: `official_api` | `public_web` | `affiliate_feed` | `community` | `disabled`

## 0.1 Hasil verifikasi 2026-11-22 — ringkasan

Diverifikasi satu per satu lewat `browser.open` ke URL listing + `robots.txt` + `browser.search` ke halaman detail.

**LAYAK (9):** BCA, BNI (via bniexperience), CIMB Niaga, AZKO, Informa, GoPay, OVO, DANA, Indomaret (bersyarat, via Klik Indomaret + katalog).
**LAYAK BERSYARAT (2):** Mandiri, BRI — listing JS-rendered / URL listing belum terkonfirmasi, detail statis.
**TIDAK LAYAK untuk scraping langsung Fase 1 (2):** Alfamart (reCAPTCHA / bot wall), Alfamidi (tidak ada URL promo resmi yang terverifikasi).

Detail per sumber ada di §1. Yang ditandai `disabled` di bawah **tidak boleh** dipaksa dengan bypass captcha atau tebak API internal yang di-`Disallow` di robots.txt.

---

## 0. Cara membaca tabel

- **Metode**: jalur resmi yang dipakai.
- **Legalitas**: penilaian awal, bukan nasihat hukum. Perlu cek ToS terbaru saat implementasi.
- **Frekuensi**: seberapa sering dicek ulang (target Fase 1: sumber resmi minimal tiap 6 jam).
- **Fase**: kapan konektor dibangun.
- **Biaya**: perkiraan awal, harus dikonfirmasi owner sebelum diaktifkan.

---

## 1. Fase 1 — MVP Surabaya (prioritas, paling stabil & legal)

Sumber-sumber ini adalah fondasi MVP. Target: ≥200 promo aktif nyata terindeks.

### 1.1 Bank — TERVERIFIKASI 2026-11-22

| Sumber | URL promo yang benar (terverifikasi) | robots.txt | Tipe halaman | Sitemap | Status |
|---|---|---|---|---|---|
| **BCA — LAYAK, vertical slice** | Listing: `https://promo.bca.co.id/` — Detail contoh: `https://promo.bca.co.id/id/all/2026/10/26/04/starting-lane` | `promo.bca.co.id/robots.txt`: `Allow: /`, `Disallow: /*/search`, Sitemap ada. `www.bca.co.id/robots.txt`: Disallow `/others/`, `/sitecore/`, `/id/Campaign/` — promo subdomain tidak dilarang. | Listing **JS-rendered** (text fetch hanya 8 baris, shell saja). Detail statis di indeks search. | Ya: `https://promo.bca.co.id/sitemap.xml` + `https://www.bca.co.id/sitemap.xml` | **LAYAK.** Discovery utama via sitemap.xml, bukan via `/*/search` (dilarang). Listing butuh Playwright, atau crawl sitemap → detail. Prioritas vertical slice. |
| **Mandiri — LAYAK BERSYARAT** | Listing: `https://www.bankmandiri.co.id/promo` — Detail contoh: `https://www.bankmandiri.co.id/payment-top-up-100-lp-november` | `User-Agent: *` `Disallow: /*.pdf$` — hanya PDF yang dilarang. Tidak ada sitemap di robots.txt. | Listing **JS-rendered** (text fetch hanya footer). Detail statis. | Tidak ada di robots.txt | **LAYAK BERSYARAT.** Jangan fetch PDF. Discovery via listing JS (Playwright) atau link detail. Cek ulang sitemap saat implementasi. |
| **BRI — LAYAK BERSYARAT** | Detail terverifikasi: `https://bri.co.id/web/guest/id/promo-detail/2229`, `https://www.bri.co.id/web/promo/detail-promo?p_p_id=BriPromoDetailPortlet…` — Listing `https://bri.co.id/web/guest/promo` **gagal dibuka** via browser.open (network error/DNS/timeout, 2026-11-22). URL listing belum terkonfirmasi. | `https://bri.co.id/robots.txt` **mengembalikan HTML homepage, bukan file robots** (404 fallback). Artinya: tidak ada robots.txt yang bisa dibaca. Perlakukan sebagai tanpa larangan eksplisit, tapi tetap sopan, rate limit ketat, cek ulang di implementasi. | Portal Liferay, kemungkinan JS/portlet. Detail statis di indeks search. | Tidak terkonfirmasi | **LAYAK BERSYARAT.** Jangan hardcode URL listing. Temukan URL listing yang benar via navigasi situs live di implementasi, simpan sebagai fixture. Kalau listing tetap tidak stabil, fallback ke detail via search/sitemap internal. |
| **BNI — LAYAK via bniexperience** | **Pakai ini:** Listing `https://bniexperience.bni.co.id/promo` — Detail: `https://bniexperience.bni.co.id/promo/detail/dapatkan-reward-hingga-rp100000-di-booth-88-baja-bprmuk` — Jangan jadikan `www.bni.co.id` sumber utama. | `bniexperience.bni.co.id/robots.txt`: `Allow: /`, `Disallow: /sliders`, `/promo/preview/*`, Sitemap ada. `www.bni.co.id/robots.txt`: **Crawl-delay: 10, Request-rate: 1/5 (1 halaman per 5 detik), Visit-time: 14:00–22:00 UTC** — sangat ketat. | Listing **HTML statis / SSR** (204 baris, filter Kategori + Daerah termasuk Surabaya, Malang). Catatan 2026-11-22: `/promo/surabaya` mengembalikan HTTP 500 di server BNI, sehingga geotag wilayah mengandalkan konten detail. | Ya: `https://bniexperience.bni.co.id/sitemap.xml` | **LAYAK.** Wajib pakai subdomain bniexperience. Jangan crawl `www.bni.co.id` di luar jam 14:00–22:00 UTC dan jangan lebih cepat dari 1 req/5 detik kalau terpaksa menyentuhnya. |
| **CIMB Niaga — LAYAK BERSYARAT** | Listing: `https://www.cimbniaga.co.id/id/personal/promo` — Detail: `https://www.cimbniaga.co.id/id/personal/promo/promo-detail.PRM-270126-00001` | `Disallow: /cgi-bin/`, `/jcr:content/*`, `/_jcr_content/*`, `/apps-content/*`, dll. Promo tidak dilarang. | Listing **JS-rendered** (AEM, text fetch hanya 16 baris). Detail statis. | Ya: `https://www.cimbniaga.co.id/sitemap.xml` | **LAYAK BERSYARAT.** Discovery via sitemap.xml. Listing butuh Playwright. |

### 1.2 Minimarket & ritel — TERVERIFIKASI 2026-11-22

| Sumber | URL promo yang benar (terverifikasi) | robots.txt | Tipe halaman | Sitemap | Status |
|---|---|---|---|---|---|
| **Indomaret (`indomaret.co.id/promosi/`) — LAYAK** | `https://www.indomaret.co.id/promosi/` (HTML statis resmi Indomaret: Super Hemat, Paling Murah, Hemat Minggu Ini, Tebus Heboh, dll.). Catatan: `klikindomaret.com/xpress/promo` memblokir remote Module Federation (`ap-mc.klikindomaret.com` mengembalikan `net::ERR_BLOCKED_BY_ORB`), sehingga tidak di-scrape. | `www.indomaret.co.id/robots.txt` mengembalikan HTML homepage (bukan file robots). `www.klikindomaret.com/robots.txt`: `Disallow: /api/`, `Allow: /`. | **HTML statis** di `indomaret.co.id/promosi/`. | `https://www.klikindomaret.com/sitemap.xml` | **LAYAK via `indomaret.co.id/promosi/`.** Konektor Indomaret memakai HTML statis resmi `indomaret.co.id/promosi/` dan tidak memanggil `/api/*` Klik Indomaret. |
| **Alfamart / Alfagift — TIDAK LAYAK scraping langsung** | Homepage `https://alfamart.co.id/` menampilkan Promo Spesial Mingguan, Promo JSM, PSM, Tebus Murah. Detail contoh: `https://alfamart.co.id/program-detail/cepat-cashback-extra-pasti-dapat` | `https://alfamart.co.id/robots.txt` **memicu reCAPTCHA "Checking your browser"** (2026-11-22). Bot wall aktif. | Tidak bisa dipastikan dari text fetch karena diblokir reCAPTCHA. | Tidak bisa dibaca karena bot wall | **TIDAK LAYAK untuk `public_web` langsung di Fase 1. Tandai `disabled` untuk konektor scraping langsung. JANGAN bypass captcha.** Alternatif: Alfagift (`https://alfagift.alfamart.co.id/news-detail/…` terverifikasi di search), IG Business Discovery (Fase 2), komunitas. Cek ulang dengan live browser di implementasi — kalau bot wall tetap ada, tetap disabled. |
| **Alfamidi — TIDAK LAYAK Fase 1** | **Tidak ada URL promo resmi yang terverifikasi.** `https://www.alfamidi.co.id/robots.txt` gagal dibuka (URL tidak resolvable via browser.open, 2026-11-22). Search hanya menemukan republikasi katalog di `katalogpromosi.com` dan `mediakompeten.co.id` (contoh: Promo HAP 16–22 Nov 2026), bukan situs resmi. | Tidak bisa dibaca — domain tidak resolvable via tool. | Tidak terverifikasi | Tidak terverifikasi | **TIDAK LAYAK Fase 1. Tandai `disabled` sementara.** Jangan pakai situs republikasi sebagai sumber utama (bukan sumber resmi, risiko salah tanggal/harga). Alternatif: Alfagift / komunitas, atau verifikasi manual via live browser di implementasi. Kalau tetap tidak ada URL resmi, tetap disabled. |
| **AZKO (eks-ACE) — LAYAK** | `https://azko.id/` + detail: `https://azko.id/promo/solusi-ringkas-bersantai-di-teras`, `https://azko.id/home-fest-gmp`, `https://azko.id/inspiration/promo-anniversary-azko-31-produk-terhemat` | `Allow: /`, `Disallow: /hc`, `/*?utm_*`, `/api/`, dll. | **HTML statis / SSR** — konten promo lengkap di text fetch/search. | Ya, tapi tidak ada sitemap promo khusus: `https://azko.id/id/homepage.xml`, `/inspirasi.xml`, `/kategori-produk.xml`, dll. | **LAYAK.** Jangan pakai `/api/` internal (dilarang). Discovery via homepage + sitemap inspirasi/homepage. |
| **Informa — LAYAK** | `https://informa.co.id/informa-wow-sale-2026/`, `https://informa.co.id/informa-early-wow-sale-2026`, `https://informa.co.id/inspirations/promo-anniversary-informa` | `Allow: /`, `Disallow: /up` | **HTML statis** — konten promo lengkap. | Ya: `https://informa.co.id/sitemap.xml` | **LAYAK.** |

### 1.3 E-wallet — TERVERIFIKASI 2026-11-22

| Sumber | URL promo yang benar (terverifikasi) | robots.txt | Tipe halaman | Sitemap | Status |
|---|---|---|---|---|---|
| **GoPay — LAYAK, prioritas tinggi** | Listing: `https://gopay.co.id/promo` — Detail: `https://gopay.co.id/promo/mini-app-travel`, `https://gopay.co.id/promo/bsi` — Blog promo juga di `https://gopay.co.id/blog/…` | `Allow: /`, `Disallow: /promo?page`, `/promo?category`, `/_nuxt/*`, `/id/`, dll. | **HTML statis / SSR (Nuxt)** — listing menampilkan "Menampilkan 1–15 promo dari 63" lengkap dengan kategori + periode + wilayah. Konektor terbaik di Fase 1. | Ya, khusus promo: `https://gopay.co.id/sitemap-promo.xml` + `sitemap.xml`, `sitemap-blog.xml` | **LAYAK.** Discovery utama via `sitemap-promo.xml`. **Jangan** crawl `/promo?page=` atau `/promo?category` (dilarang di robots). |
| **OVO — LAYAK BERSYARAT** | Listing: `https://ovo.id/deals` — Detail: `https://ovo.id/deals/view/43221`, `https://ovo.id/deals/view/42710` | `Allow: *.js, *.css`, `Disallow: */page/*`, `*/?s=*`, `*/?*` — **query string dilarang**. | Listing HTML (judul saja, 38 baris). Detail statis di search. | Ya: `https://www.ovo.id/sitemap.xml` | **LAYAK BERSYARAT.** Strip semua query param (UTM, `__cf_chl_*`) dari URL detail sebelum disimpan. Jangan crawl URL ber-query. |
| **DANA — DISABLED (WAF/timeout)** | Listing: `https://www.dana.id/promo` | `User-agent: *` `Disallow:` (kosong). | Koneksi langsung `httpx`/`curl` ditolak (`Empty reply` / timeout), dan Playwright Chromium juga mengalami `Timeout 30000ms` / `ERR_CONNECTION_RESET` berulang saat verifikasi 2026-11-22. | `https://www.dana.id/sitemap.xml` (tidak dapat diambil otomatis tanpa diblokir WAF) | **`disabled`.** Alasan: koneksi langsung ditolak (WAF), Playwright juga diblokir/timeout. Alternatif: akun IG resmi `@dana.id` via Business Discovery (Fase 2) + kiriman komunitas / PWA Share Target. |
| ShopeePay / LinkAja | Belum diverifikasi di revisi ini — verifikasi menyusul setelah 3 e-wallet utama stabil. | Belum diverifikasi | Belum diverifikasi | Belum diverifikasi | **Tunda.** Jangan dibangun sebelum verifikasi seperti di atas. |

> Catatan: pilih **3 e-wallet utama dulu** (GoPay, OVO, DANA) di Fase 1. ShopeePay & LinkAja menyusul bila kapasitas cukup dan sudah diverifikasi.

### 1.4 Komunitas (Fase 1, legal & kuat)

| Sumber | Jalur | Metode | Legalitas | Frekuensi | Biaya | Catatan |
|---|---|---|---|---|---|---|
| Form kirim promo | Form di web + Cloudflare Turnstile | `community` | Legal, kiriman pengguna dengan moderasi. | Real-time (antrean moderasi) | Gratis | Link + foto opsional, rate limit per pengguna. |
| PWA Share Target | Share dari IG/X/TikTok → BuruPromo | `community` | Legal, pengguna membagikan link yang ia lihat. | Real-time (antrean moderasi) | Gratis | Cara menangkap promo dari aplikasi tertutup tanpa scraping aplikasi. |

---

## 2. Fase 2 — Media sosial via API resmi

**Jangan bangun konektor ini sebelum Fase 1 stabil dan App Review / persetujuan owner jelas.**

### 2.1 X (Twitter)

| Item | Detail |
|---|---|
| Jalur | API resmi v2, recent search |
| Metode | `official_api` |
| Query contoh | `(promo OR diskon OR voucher) (surabaya OR sby) lang:in -is:retweet` |
| Biaya | **Pay-per-use berbasis kredit, ± $0,005 per post yang dibaca**, batas ±3 juta post reads/bulan. Wajib **budget cap harian** + cache + query spesifik. |
| Legalitas | API resmi, tapi berbayar. Harus ada budget yang disetujui owner dulu. |
| Frekuensi | Tergantung budget, mis. tiap 1–2 jam untuk query Surabaya, bukan semua query. |
| Risiko | Biaya membengkak kalau query terlalu luas. Budget guard wajib menghentikan job otomatis. |

### 2.2 Threads

| Item | Detail |
|---|---|
| Jalur | Threads API `/keyword_search` |
| Metode | `official_api` |
| Izin | `threads_keyword_search` |
| Legalitas | API resmi. **Sebelum app di-approve, search hanya mencakup post milik akun sendiri** — jadi fase awal pakai mode terbatas, ajukan App Review. |
| Frekuensi | Setelah approve: tiap 2–4 jam untuk keyword Surabaya. |
| Catatan | Jangan mengandalkan Threads sebagai sumber utama sebelum App Review lolos. |

### 2.3 Instagram

| Item | Detail |
|---|---|
| Jalur | Graph API: **Business Discovery** + **Hashtag Search** |
| Metode | `official_api` |
| Business Discovery | Ambil post terbaru dari akun bisnis/creator yang dikurasi: @indomaret, @alfamart, @informa_id, akun kuliner Surabaya, dll. |
| Hashtag Search | Butuh App Review fitur *Instagram Public Content Access*, dan **maksimal 30 hashtag unik per 7 hari per akun bisnis**. Pilih hashtag dengan cermat (#promosurabaya, #kulinersurabaya, #promomakanan, dll.) dan rotasi. |
| Batasan | Story **tidak didukung**. |
| Frekuensi | Business Discovery: tiap 4–6 jam per akun kurasi. Hashtag: sesuai kuota rotasi. |
| Catatan | Daftar akun & hashtag dikelola admin, dengan penghitung kuota di `/admin`. |

### 2.4 Reddit

| Item | Detail |
|---|---|
| Jalur | Data API resmi (OAuth) |
| Metode | `official_api` |
| Subreddit awal | r/indonesia, r/surabaya, r/finansial |
| Legalitas | Akses sekarang **harus di-approve**, gratis hanya untuk **non-komersial**; penggunaan komersial butuh perjanjian dengan Reddit. Mulai mode non-komersial; kalau nanti produk dimonetisasi, matikan atau urus lisensi. |
| Frekuensi | Tiap 4–6 jam. |
| Catatan | Tandai status konektor dengan jelas di admin bila status komersial berubah. |

### 2.5 Telegram (opsional)

| Item | Detail |
|---|---|
| Jalur | Kanal publik promo via API resmi |
| Metode | `official_api` |
| Legalitas | Hanya kanal publik. |
| Frekuensi | Tiap 2–4 jam. |
| Catatan | Opsional Fase 2 akhir, bukan prioritas. |

---

## 3. Fase 4 — E-commerce & afiliasi (sumber + monetisasi)

**Jangan bangun sebagai sumber utama sebelum Fase 1–3 stabil.**

| Sumber | Jalur | Metode | Legalitas | Catatan |
|---|---|---|---|---|
| Shopee | Program afiliasi resmi + halaman promo publik | `affiliate_feed` + `public_web` | Afiliasi sekaligus jadi sumber monetisasi. Jangan scrape aplikasi. | Halaman event tanggal kembar, flash sale, gratis ongkir. |
| Tokopedia / TikTok Shop | Program afiliasi resmi + halaman promo publik | `affiliate_feed` + `public_web` | Sama seperti Shopee. | Tokopedia & TikTok Shop kini satu ekosistem, cek struktur afiliasi terbaru. |
| Lazada | Program afiliasi + halaman promo publik | `affiliate_feed` + `public_web` | Afiliasi resmi. | — |
| Blibli | Program afiliasi + halaman promo publik | `affiliate_feed` + `public_web` | Afiliasi resmi. | — |
| Bukalapak | Cek status | `disabled` (sementara) | Bukalapak sudah berhenti jualan barang fisik dan fokus ke produk virtual (pulsa, tagihan). Masukkan hanya kalau masih relevan. | Cek ulang sebelum Fase 4. |

---

## 4. Sumber lain — F&B, delivery, ritel tambahan

| Sumber | Jalur | Metode | Legalitas | Fase | Catatan |
|---|---|---|---|---|---|
| GoFood, GrabFood, ShopeeFood | Halaman promo publik + IG resmi brand | `public_web` + `official_api` (IG) | Halaman publik + pengumuman publik. Promo in-app tidak di-scrape; andalkan pengumuman publik + kiriman komunitas. | Fase 1 akhir / Fase 2 | Brand kopi/fast food juga lewat jalur yang sama. |
| Hypermart, Superindo, Lotte Grosir, Indogrosir | Halaman promo & katalog publik + IG resmi | `public_web` + OCR | Halaman publik, katalog sering gambar/PDF. | Fase 1 akhir / Fase 2 | Prioritaskan setelah Indomaret/Alfamart stabil. |
| IKEA | Halaman promo publik | `public_web` | Halaman publik. | Fase 2+ | Rumah & perabot. |
| Bank & e-wallet lain | BSI, Jago, SeaBank, dll. — halaman promo publik | `public_web` | Halaman publik. | Fase 1 akhir | Tambah setelah 5 bank utama stabil. |

---

## 5. Yang sengaja TIDAK dilakukan

| Praktik | Alasan | Alternatif |
|---|---|---|
| Scrape aplikasi (TikTok, Shopee app, GoFood app, dll.) | Melanggar ToS, butuh login, rawan blokir. | Feed afiliasi resmi + halaman promo publik + komunitas. |
| Bypass login / captcha / anti-bot | Dilarang di prompt master §2. | Tandai `disabled`, pakai jalur resmi atau komunitas. |
| Akun palsu / cookie / session curian | Dilarang, melanggar UU PDP & ToS. | Tidak ada alternatif — jangan dilakukan. |
| Salin postingan utuh | Hak cipta. | Ringkasan terstruktur + link sumber + thumbnail kecil. |
| Simpan data pribadi pemilik postingan | UU PDP. | Hanya handle publik & URL. |

---

## 6. Aturan operasional per konektor

Setiap konektor wajib punya di `sources`:
- `type`, `status` (aktif / paused / disabled), `schedule`, `quota / budget harian`
- `last_success_at`, `last_error`, `promo_baru_terakhir`, `waktu_respons`
- Feature flag & kill switch di `/admin`
- **Fixture test WAJIB untuk setiap konektor sejak Fase 1** (lihat ARCHITECTURE.md §12.1): setiap konektor harus punya `services/ingest/connectors/tests/fixtures/<source>/listing.html` + minimal 2 `detail.html` + `expected.json` yang disimpan di repo. Test parser **tidak boleh** melakukan request live. Konektor tanpa fixture tidak boleh merge.
- Budget guard untuk konektor berbayar (X, LLM): berhenti otomatis saat batas tercapai, alert ke admin. **X: budget $0 — tidak diaktifkan sampai Fase 2 (keputusan owner 2026-11-22).**

Frekuensi default:
- Sumber resmi (bank, minimarket, e-wallet): **tiap 6 jam**, promo "segera berakhir" (<24 jam) dicek lebih sering
- Media sosial API resmi: **tiap 1–6 jam** tergantung budget & kuota
- Komunitas: **real-time ke antrean moderasi**, bukan langsung tayang
- Expire job: **tiap 10 menit**

---

## 7. Daftar periksa sebelum mengaktifkan sebuah konektor

- [ ] URL & metode sudah dicek ulang (ToS bisa berubah)
- [ ] `robots.txt` dihormati (untuk `public_web`)
- [ ] Rate limit & User-Agent jujur sudah diatur
- [ ] Budget / kuota sudah disetujui owner (untuk yang berbayar)
- [ ] Fixture test sudah dibuat
- [ ] Kill switch & health check sudah ada di admin
- [ ] Tidak ada login / captcha yang harus di-bypass

---

*Perubahan katalog dicatat di sini + di `sources` DB. Kalau sebuah sumber berubah aturan, update file ini dulu sebelum mengubah kode konektor.*
