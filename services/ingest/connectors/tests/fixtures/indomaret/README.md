# Fixture Indomaret (`indomaret.co.id/promosi/`)

- Diambil langsung dari `https://www.indomaret.co.id/promosi/` (HTML statis resmi Indomaret) pada 2026-11-23 WIB.
- Catatan teknis: `klikindomaret.com/xpress/promo` gagal memuat bundle remote Module Federation (`ap-mc.klikindomaret.com` diblokir `net::ERR_BLOCKED_BY_ORB`), sehingga konektor menggunakan halaman promosi resmi statis di `indomaret.co.id/promosi/`.
- `listing.html`: HTML penuh `https://www.indomaret.co.id/promosi/` (10 bagian promo).
- `detail-1.html`: bagian `Super Hemat` (Periode 12–25 November 2026).
- `detail-2.html`: bagian `Tebus Heboh` (Periode 12–25 November 2026).
- `expected.json`: ekspektasi parser dan ekstraktor aturan untuk fixture di atas.
