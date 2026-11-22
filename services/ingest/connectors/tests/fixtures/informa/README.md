# Fixture Informa (`informa.co.id`)

- Diambil langsung dari `https://informa.co.id/home-promotion` menggunakan Playwright Chromium pada 2026-11-23 WIB (halaman dirender Nuxt/SPA di sisi klien).
- `listing.html`: hasil render DOM `https://informa.co.id/home-promotion` (6 tautan `/home-promotion/*`).
- `detail-1.html`: `https://informa.co.id/home-promotion/informa-electronics-black-friday` (Diskon hingga 40%, berakhir 30 November 2026).
- `detail-2.html`: `https://informa.co.id/home-promotion/informa-chair-vaganza` (Hemat hingga 50%, berakhir 30 November 2026).
- `expected.json`: ekspektasi parser dan ekstraktor aturan untuk fixture di atas.
