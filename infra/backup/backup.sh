#!/usr/bin/env bash
# BuruPromo — backup DB harian ke Google Drive via rclone (ARCH §3.5.2, Rp0).
# Cron 02:00 WIB (lihat crontab.example). JANGAN isi kredensial rclone di sini
# atau di repo — rclone remote "gdrive" dikonfigurasi owner di VM via
# `rclone config` (token OAuth ada di ~/.config/rclone/rclone.conf, di luar repo).
# Isi: pg_dump -> gzip -> rclone copy -> verifikasi -> prune retensi.
# Retensi: 7 harian + 4 mingguan (file Minggu masuk folder weekly/).
# Restore WAJIB diuji sekali di Fase 0 ke DB lokal (lihat README.md) — jangan
# klaim backup jalan tanpa pernah restore.
set -euo pipefail

# COMPOSE_ARGS: daftar file compose, mis. "-f infra/docker-compose.yml"
# (lokal) atau "-f infra/docker-compose.yml -f infra/docker-compose.prod.yml"
# (produksi). JANGAN isi hanya prod.yml — itu file override, bukan standalone.
COMPOSE_ARGS="${COMPOSE_ARGS:--f infra/docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/burupromo}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:BuruPromo/backups}"
POSTGRES_DB="${POSTGRES_DB:-burupromo}"
POSTGRES_USER="${POSTGRES_USER:-burupromo}"
DATE="$(date +%Y-%m-%d_%H%M)"
DOW="$(date +%u)"  # 1=Senin .. 7=Minggu
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly"
log() { echo "[$(date -Is)] $*" | tee -a "${LOG_FILE}"; }

log "Backup mulai: ${DATE}"
DUMP="${BACKUP_DIR}/daily/db-${DATE}.sql.gz"

# pg_dump dari container postgres (jangan dump dari host tanpa password).
# shellcheck disable=SC2086 — COMPOSE_ARGS sengaja dipecah jadi beberapa -f.
docker compose ${COMPOSE_ARGS} exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${DUMP}"
gzip -t "${DUMP}" || { log "GAGAL: file gzip rusak: ${DUMP}"; exit 1; }
log "Dump OK: ${DUMP} ($(du -h "${DUMP}" | cut -f1))"

# Salin ke Google Drive (jatah gratis 15 GB/akun).
rclone copy "${DUMP}" "${RCLONE_REMOTE}/daily/" || { log "GAGAL: rclone copy daily"; exit 1; }
if [ "${DOW}" = "7" ]; then
  cp "${DUMP}" "${BACKUP_DIR}/weekly/"
  rclone copy "${DUMP}" "${RCLONE_REMOTE}/weekly/" || { log "GAGAL: rclone copy weekly"; exit 1; }
  log "Salinan mingguan dibuat (Minggu)."
fi

# Prune retensi lokal + remote.
find "${BACKUP_DIR}/daily" -name 'db-*.sql.gz' -mtime +7 -delete
find "${BACKUP_DIR}/weekly" -name 'db-*.sql.gz' -mtime +28 -delete
rclone delete "${RCLONE_REMOTE}/daily" --min-age 7d || log "Peringatan: prune remote daily gagal"
rclone delete "${RCLONE_REMOTE}/weekly" --min-age 28d || log "Peringatan: prune remote weekly gagal"

log "Backup selesai: ${DATE}"
