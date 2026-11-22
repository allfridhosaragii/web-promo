# Fixture BCA — SINTETIS / PLACEHOLDER (WAJIB diganti di vertical slice)

**Fixture di folder ini saat ini SINTETIS — dikarang untuk test parser, BUKAN
HTML asli dari promo.bca.co.id.** Jangan anggap promo di sini nyata. Jangan
pakai file ini untuk produksi, demo, atau klaim "promo BCA sudah diambil".

## Isi saat ini

| File | Status |
|---|---|
| `listing.html` | Sintetis. Link detail meniru pola URL asli dari sitemap, tapi daftarnya karangan. |
| `detail-1.html` | Sintetis. "Starting Lane" memang halaman nyata, tapi isi file (diskon, kode, tanggal) karangan. |
| `detail-2.html` | Sintetis. "Contoh Promo Kopi Surabaya" adalah promo karangan sepenuhnya. |
| `expected.json` | Berasal dari data karangan di atas — BUKAN data asli. Jangan disajikan sebagai data asli. |

## Yang WAJIB dilakukan di vertical slice BCA

1. Ambil `listing` asli: discovery via `https://promo.bca.co.id/sitemap.xml`,
   lalu simpan HTML listing asli sebagai `listing.html` (ganti file ini).
2. Simpan minimal 2 halaman detail ASLI sebagai `detail-1.html` dan
   `detail-2.html` (ganti file ini).
3. Tulis `expected.json` dari DATA ASLI halaman tersebut (judul, nilai, tanggal
   WIB, kode voucher, region) — bukan dari karangan.
4. Tulis atribusi URL sumber di header tiap file HTML (URL persis halaman
   yang disimpan + tanggal simpan).
5. Jalankan `pytest` + `python3 services/ingest/scripts/check_fixtures.py`
   setelah penggantian — test harus tetap hijau dengan data asli.

Aturan umum (ARCHITECTURE.md §12.1): fixture diambil dari halaman publik yang
sudah diverifikasi di SOURCES.md, disimpan sebagai file untuk test saja, dengan
atribusi URL sumber di header file. Test tidak pernah fetch live.
