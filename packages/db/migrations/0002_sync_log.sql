-- 0002_sync_log — tabel audit sinkron Spreadsheet (ARCH §17.5, revisi 2).
-- Sumber kebenaran audit sinkron; sheet "Log Sinkron" hanya cerminnya.
-- Dijalankan setelah 0001_init.sql (butuh tabel promos).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sync_action') THEN
    CREATE TYPE sync_action AS ENUM ('upsert', 'pindah_arsip', 'hapus', 'retry', 'gagal');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sync_status') THEN
    CREATE TYPE sync_status AS ENUM ('ok', 'gagal', 'antre');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  promo_id UUID REFERENCES promos(id),
  sheet VARCHAR(50) NOT NULL,
  action sync_action NOT NULL,
  status sync_status NOT NULL,
  error TEXT,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sync_log_promo_idx ON sync_log (promo_id);
CREATE INDEX IF NOT EXISTS sync_log_attempted_idx ON sync_log (attempted_at);
