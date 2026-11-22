# Fixture OVO (`ovo.id/deals`)

- Diambil langsung dari `https://ovo.id/deals` menggunakan Playwright Chromium (halaman listing memuat daftar deal via JS) dan halaman detail statisnya via `httpx` pada 2026-11-23 WIB.
- `listing.html`: hasil render DOM `https://ovo.id/deals` (9 tautan `/deals/view/*`).
- `detail-1.html`: `https://ovo.id/deals/view/42710` (Promo belanja online s/d Rp250rb).
- `detail-2.html`: `https://ovo.id/deals/view/42727` (Ada QRIS, ada OVO, ada promo!).
- `expected.json`: ekspektasi parser dan ekstraktor aturan untuk fixture di atas.
