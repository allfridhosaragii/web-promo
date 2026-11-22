-- 0003_split_status — pisah status tunggal jadi lifecycle + moderation (A4)
-- + kolom last_confirmed_at untuk promo tanpa ends_at (A5).
-- Dijalankan setelah 0002_sync_log.sql. Idempotent (IF NOT EXISTS).
-- Pemetaan dari kolom `status` lama:
--   aktif             -> lifecycle aktif,            moderation belum_ditinjau
--   segera_berakhir   -> lifecycle segera_berakhir,  moderation belum_ditinjau
--   kedaluwarsa       -> lifecycle kedaluwarsa,      moderation belum_ditinjau
--   belum_terverifikasi -> lifecycle dijadwalkan,    moderation belum_ditinjau
--   dilaporkan        -> lifecycle aktif,            moderation dilaporkan
--   ditolak           -> lifecycle aktif,            moderation ditolak
--                       (ditolak tetap 404 di API + tidak masuk index utama)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'promo_lifecycle') THEN
    CREATE TYPE promo_lifecycle AS ENUM ('dijadwalkan', 'aktif', 'segera_berakhir', 'kedaluwarsa');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'promo_moderation') THEN
    CREATE TYPE promo_moderation AS ENUM ('belum_ditinjau', 'terverifikasi', 'dilaporkan', 'ditolak');
  END IF;
END $$;

ALTER TABLE promos ADD COLUMN IF NOT EXISTS lifecycle promo_lifecycle NOT NULL DEFAULT 'dijadwalkan';
ALTER TABLE promos ADD COLUMN IF NOT EXISTS moderation promo_moderation NOT NULL DEFAULT 'belum_ditinjau';
ALTER TABLE promos ADD COLUMN IF NOT EXISTS last_confirmed_at TIMESTAMPTZ;

-- Migrasi data hanya bila kolom `status` lama masih ada.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'promos' AND column_name = 'status') THEN
    UPDATE promos SET
      lifecycle = CASE status
        WHEN 'aktif' THEN 'aktif'::promo_lifecycle
        WHEN 'segera_berakhir' THEN 'segera_berakhir'::promo_lifecycle
        WHEN 'kedaluwarsa' THEN 'kedaluwarsa'::promo_lifecycle
        WHEN 'belum_terverifikasi' THEN 'dijadwalkan'::promo_lifecycle
        ELSE 'aktif'::promo_lifecycle
      END,
      moderation = CASE status
        WHEN 'dilaporkan' THEN 'dilaporkan'::promo_moderation
        WHEN 'ditolak' THEN 'ditolak'::promo_moderation
        ELSE 'belum_ditinjau'::promo_moderation
      END;
    ALTER TABLE promos DROP COLUMN IF EXISTS status;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS promos_lifecycle_idx ON promos (lifecycle);
CREATE INDEX IF NOT EXISTS promos_moderation_idx ON promos (moderation);
DROP INDEX IF EXISTS promos_status_idx;
DROP TYPE IF EXISTS promo_status;
