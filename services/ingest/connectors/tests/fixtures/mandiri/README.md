# Fixture Bank Mandiri (`mandirikartukredit.com/hot-offer`)

- Diambil langsung via `httpx` dari portal resmi Mandiri Kartu Kredit `https://www.mandirikartukredit.com/hot-offer` pada 2026-11-23 WIB (HTML statis, 28 tautan `/hot-offer/*`, tanpa Playwright).
- Catatan: `www.bankmandiri.co.id/promo` hanya berisi navigasi dan menautkan ke `https://www.mandirikartukredit.com/hot-offer` untuk daftar promo kartu kredit/debit Mandiri.
- `listing.html`: `https://www.mandirikartukredit.com/hot-offer`.
- `detail-1.html`: `https://www.mandirikartukredit.com/hot-offer/promo-boga-group-hemat-20` (Hemat 20% di Boga Group).
- `detail-2.html`: `https://www.mandirikartukredit.com/hot-offer/diskon-hingga-rp-200-000-diskon-hingga-20-tukar-livin-poin-di-gyukaku` (Diskon hingga 20% Tukar Livin'poin di Gyu Kaku, min. Rp500.000).
- `expected.json`: ekspektasi parser dan ekstraktor aturan untuk fixture di atas.
