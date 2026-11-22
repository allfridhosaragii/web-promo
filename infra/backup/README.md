# Backup — rclone → Google Drive (gratis, ARCH §3.5.2)

## Cara kerja

`backup.sh` (cron 02:00 WIB, lihat `crontab.example`):
`pg_dump` dari container postgres → gzip → `rclone copy` ke Google Drive
owner → verifikasi gzip → prune. Retensi: **7 harian + 4 mingguan**
(file Minggu juga masuk folder `weekly/`).

## Setup (sekali, di VM Oracle — BUKAN di repo)

```bash
rclone config        # buat remote bernama "gdrive" (Google Drive, OAuth owner)
# JANGAN commit ~/.config/rclone/rclone.conf — token OAuth ada di sana.
chmod +x infra/backup/backup.sh
crontab infra/backup/crontab.example   # atau salin isinya ke crontab -e
```

## Uji restore (WAJIB sekali di Fase 0 — jangan klaim backup jalan tanpa ini)

```bash
# 1. Ambil file backup terbaru dari Drive (atau dari /var/backups/burupromo/daily).
rclone copy gdrive:BuruPromo/backups/daily/db-TERBARU.sql.gz /tmp/
# 2. Restore ke database LOKAL yang kosong (bukan produksi!).
gunzip -c /tmp/db-TERBARU.sql.gz | docker compose exec -T postgres \
  psql -U burupromo -d burupromo_restore
# 3. Cek: tabel promos/regions ada + jumlah baris masuk akal.
# 4. Catat tanggal uji restore di sini:
#    Uji restore: BELUM DIUJI (isi tanggal + hasil setelah diuji).
```

## Yang TIDAK di-backup

- `.env` berisi secret — secret tidak pernah di-backup ke Drive.
- File JSON service account / kredensial — simpan di luar repo, di VM saja.
- Yang ikut dibackup (bersama dump): `infra/meilisearch/settings.json`,
  `packages/db/seed/`, `.env.example` — salin manual bila perlu
  (bukan bagian dari `backup.sh`).
