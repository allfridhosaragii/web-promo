-- 0001_init — BuruPromo Fase 0. Dibuat dari packages/db/src/schema.ts.
-- Catatan: CREATE EXTENSION vector hanya jalan bila pgvector terpasang
-- (lihat infra/postgres/Dockerfile). Kalau gagal, komentar baris itu dan
-- kolom embedding tetap TEXT sementara — jangan pura-pura ada pgvector.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE region_level AS ENUM ('provinsi', 'kab_kota', 'kecamatan');
CREATE TYPE promo_type AS ENUM ('persen', 'potongan_nominal', 'cashback', 'beli_x_gratis_y', 'gratis_ongkir', 'harga_spesial', 'bundling', 'poin', 'cicilan_0', 'lainnya');
CREATE TYPE promo_lifecycle AS ENUM ('dijadwalkan', 'aktif', 'segera_berakhir', 'kedaluwarsa');
CREATE TYPE promo_moderation AS ENUM ('belum_ditinjau', 'terverifikasi', 'dilaporkan', 'ditolak');
CREATE TYPE region_scope AS ENUM ('nasional', 'provinsi', 'kota', 'outlet_tertentu');
CREATE TYPE channel AS ENUM ('online', 'offline', 'keduanya');
CREATE TYPE source_type AS ENUM ('official_api', 'public_web', 'affiliate_feed', 'community', 'disabled');
CREATE TYPE user_role AS ENUM ('user', 'moderator', 'admin');

CREATE TABLE regions (
  code VARCHAR(20) PRIMARY KEY, code_bps VARCHAR(20), name TEXT NOT NULL,
  level region_level NOT NULL, parent_code VARCHAR(20), cluster VARCHAR(100), geom TEXT
);
CREATE INDEX regions_parent_idx ON regions (parent_code);
CREATE INDEX regions_cluster_idx ON regions (cluster);

CREATE TABLE region_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), slug VARCHAR(100) NOT NULL UNIQUE,
  name TEXT NOT NULL, province_code VARCHAR(20) NOT NULL
);
CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), slug VARCHAR(100) NOT NULL UNIQUE,
  name TEXT NOT NULL, parent_id UUID, sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL,
  slug VARCHAR(100) NOT NULL UNIQUE, logo_url TEXT, category_slug VARCHAR(100),
  website TEXT, social_handles JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE outlets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), brand_id UUID NOT NULL REFERENCES brands(id),
  name TEXT NOT NULL, address TEXT, region_code VARCHAR(20) NOT NULL,
  lat DOUBLE PRECISION, lon DOUBLE PRECISION
);
CREATE INDEX outlets_brand_idx ON outlets (brand_id);
CREATE INDEX outlets_region_idx ON outlets (region_code);

CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_id VARCHAR(100) NOT NULL UNIQUE,
  name TEXT NOT NULL, type source_type NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'disabled',
  enabled BOOLEAN NOT NULL DEFAULT FALSE, schedule_cron VARCHAR(50) DEFAULT '0 */6 * * *',
  budget_daily_usd REAL NOT NULL DEFAULT 0, base_url TEXT,
  last_success_at TIMESTAMPTZ, last_error TEXT, last_latency_ms INTEGER
);
-- Seed status konektor Fase 0: SEMUA disabled, kecuali komunitas (form) yang belum aktif.
-- X: budget $0, disabled. Alfamart & Alfamidi: disabled (SOURCES.md Rev 1).
INSERT INTO sources (source_id, name, type, status, enabled, base_url) VALUES
  ('bca', 'BCA', 'public_web', 'disabled', FALSE, 'https://promo.bca.co.id/'),
  ('gopay', 'GoPay', 'public_web', 'disabled', FALSE, 'https://gopay.co.id/promo'),
  ('dana', 'DANA', 'public_web', 'disabled', FALSE, 'https://www.dana.id/promo'),
  ('ovo', 'OVO', 'public_web', 'disabled', FALSE, 'https://ovo.id/deals'),
  ('bni', 'BNI (bniexperience)', 'public_web', 'disabled', FALSE, 'https://bniexperience.bni.co.id/promo'),
  ('azko', 'AZKO', 'public_web', 'disabled', FALSE, 'https://azko.id/'),
  ('informa', 'Informa', 'public_web', 'disabled', FALSE, 'https://informa.co.id/'),
  ('alfamart', 'Alfamart', 'disabled', 'disabled', FALSE, 'https://alfamart.co.id/'),
  ('alfamidi', 'Alfamidi', 'disabled', 'disabled', FALSE, NULL),
  ('x', 'X (Twitter)', 'official_api', 'disabled', FALSE, NULL)
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE raw_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_id VARCHAR(100) NOT NULL,
  source_url TEXT NOT NULL, title TEXT, text TEXT NOT NULL, html TEXT,
  media_urls JSONB NOT NULL DEFAULT '[]', content_hash VARCHAR(64),
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX raw_items_source_idx ON raw_items (source_id);
CREATE INDEX raw_items_fetched_idx ON raw_items (fetched_at);
CREATE UNIQUE INDEX raw_items_hash_idx ON raw_items (content_hash);

CREATE TABLE promos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title TEXT NOT NULL, summary TEXT NOT NULL,
  promo_type promo_type NOT NULL, value_percent REAL, value_amount INTEGER,
  max_discount INTEGER, min_purchase INTEGER, voucher_code VARCHAR(100),
  how_to_claim TEXT, payment_methods JSONB NOT NULL DEFAULT '[]',
  requirements JSONB NOT NULL DEFAULT '[]', channel channel NOT NULL DEFAULT 'online',
  platform VARCHAR(100), category_ids JSONB NOT NULL DEFAULT '[]',
  brand_id UUID REFERENCES brands(id), region_scope region_scope NOT NULL DEFAULT 'nasional',
  region_codes JSONB NOT NULL DEFAULT '[]', starts_at TIMESTAMPTZ, ends_at TIMESTAMPTZ,
  recurring_rule VARCHAR(200), recurrence_end TIMESTAMPTZ, quota_note TEXT,
  source_id VARCHAR(100) NOT NULL, source_url TEXT NOT NULL, evidence_image_url TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  lifecycle promo_lifecycle NOT NULL DEFAULT 'dijadwalkan',
  moderation promo_moderation NOT NULL DEFAULT 'belum_ditinjau',
  last_checked_at TIMESTAMPTZ, last_confirmed_at TIMESTAMPTZ,
  votes_valid INTEGER NOT NULL DEFAULT 0,
  votes_invalid INTEGER NOT NULL DEFAULT 0, views INTEGER NOT NULL DEFAULT 0,
  saves INTEGER NOT NULL DEFAULT 0, dedup_key VARCHAR(200), embedding TEXT,
  is_seed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX promos_lifecycle_idx ON promos (lifecycle);
CREATE INDEX promos_moderation_idx ON promos (moderation);
CREATE INDEX promos_ends_at_idx ON promos (ends_at);
CREATE INDEX promos_brand_idx ON promos (brand_id);
CREATE INDEX promos_source_idx ON promos (source_id);
CREATE UNIQUE INDEX promos_dedup_idx ON promos (dedup_key);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) NOT NULL UNIQUE,
  name TEXT, role user_role NOT NULL DEFAULT 'user', reputation INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE saved_promos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  promo_id UUID NOT NULL REFERENCES promos(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, promo_id)
);
CREATE TABLE saved_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  query TEXT, category_slug VARCHAR(100), region_code VARCHAR(20),
  notify_via JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE wallet_preferences (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  banks JSONB NOT NULL DEFAULT '[]', ewallets JSONB NOT NULL DEFAULT '[]'
);
CREATE TABLE submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  source_url TEXT NOT NULL, title TEXT, note TEXT, photo_url TEXT,
  status VARCHAR(30) NOT NULL DEFAULT 'menunggu_moderasi', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  promo_id UUID NOT NULL REFERENCES promos(id), reason VARCHAR(50) NOT NULL, note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  promo_id UUID NOT NULL REFERENCES promos(id), vote VARCHAR(10) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (user_id, promo_id)
);
CREATE TABLE moderation_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), actor_id UUID REFERENCES users(id),
  action VARCHAR(50) NOT NULL, target_type VARCHAR(50) NOT NULL, target_id UUID, note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE promo_sources (
  promo_id UUID NOT NULL REFERENCES promos(id), source_id VARCHAR(100) NOT NULL,
  source_url TEXT NOT NULL, UNIQUE (promo_id, source_id)
);
