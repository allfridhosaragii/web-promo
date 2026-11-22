# Fixture CIMB Niaga (`cimbniaga.co.id`)

- Diambil langsung dari `https://www.cimbniaga.co.id/sitemap/promo.xml` dan halaman detail statisnya pada 2026-11-23 WIB.
- `listing.html`: isi asli `https://www.cimbniaga.co.id/sitemap/promo.xml` (1.674 URL promo, 714 URL `/id/personal/promo/promo-detail.*`).
- `detail-1.html`: `https://www.cimbniaga.co.id/id/personal/promo/promo-detail.PRM-141026-00001` (Daily Deals di Tokopedia — Diskon 10%, min. Rp500.000, 11–24 Nov 2026).
- `detail-2.html`: `https://www.cimbniaga.co.id/id/personal/promo/promo-detail.PRM-191026-00002` (Mall Day Mega Deals Setiap Kamis di Tokopedia — Diskon 20%, min. Rp350.000, 5–26 Nov 2026).
- `expected.json`: ekspektasi parser dan ekstraktor aturan untuk fixture di atas.
