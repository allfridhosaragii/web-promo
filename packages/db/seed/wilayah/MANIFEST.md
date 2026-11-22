# MANIFEST — Seed Wilayah Jawa Timur

- Sumber hukum: **Kepmendagri 300.2.2-2138/2025** (Keputusan Menteri Dalam Negeri
  tentang Kode dan Data Wilayah Administrasi Pemerintahan, berlaku 2025-06-23).
  Aturan pemberian kode: Permendagri 58/2021.
- Sumber siap-mesin (utama): Indonesia Region API (proyek independen, turunan
  dokumen resmi, bukan API resmi pemerintah) — dataset
  `kepmendagri-300.2.2-2138-2025+2430-2025`.
  Pembanding: GitHub SalzBytes/wilayah_indonesia (relasi kode BPS + Kemendagri 2025).
- File: `kepmendagri-300.2.2-2138-2025.csv`
- SHA-256: `9688e25ab5ec3b7fe50bf97bca38489bb0eeb654aaf2bb5a251ed23b423e6e52`
- Tanggal snapshot: 2026-11-22
- Isi: 1 provinsi (35 Jawa Timur) + **38 kab/kota** (29 kabupaten 35.01–35.29,
  9 kota 35.71–35.79). Seed **gagal** kalau jumlah kab/kota bukan 38.
- `code` utama = `code_dagri`. `code_bps` belum diisi di snapshot ini — ditambah
  saat cek silang BPS selesai (bukan blocker Fase 0).
- **Geometri: BELUM ADA (kekurangan yang diketahui).** Kolom `geom` NULL untuk
  semua baris di Fase 0. Sumber geometri yang direncanakan: poligon BIG
  (Badan Informasi Geospasial), digabung berdasarkan kode yang sama
  (field BIG KDPPUM/KDPKAB/KDCPUM/KDEPUM), + pencocokan BPS SIG
  https://sig.bps.go.id/bridging-kode/index. Geometri tingkat provinsi +
  kab/kota ditargetkan sebelum fitur "promo dekat saya" (Fase 3).
  Jangan pura-pura ada geometri — query radius di Fase 0 tidak dipakai.
- Jangan fetch live dari API wilayah saat runtime. Seed adalah data di repo.
