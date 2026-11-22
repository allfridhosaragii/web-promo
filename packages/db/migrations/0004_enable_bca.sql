-- 0004_enable_bca — Vertical Slice BCA: aktifkan sumber BCA + seed brand BCA & taksonomi kategori (ARCH §7).
UPDATE sources
SET status = 'public_web', enabled = TRUE
WHERE source_id = 'bca';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('BCA', 'bca', 'keuangan', 'https://promo.bca.co.id/')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO categories (slug, name, sort_order) VALUES
  ('makanan-minuman', 'Makanan & Minuman', 1),
  ('kebutuhan-harian', 'Kebutuhan Harian', 2),
  ('fashion', 'Fashion', 3),
  ('rumah-perabot', 'Rumah & Perabot', 4),
  ('elektronik-gadget', 'Elektronik & Gadget', 5),
  ('kecantikan-perawatan', 'Kecantikan & Perawatan', 6),
  ('ecommerce', 'E-commerce', 7),
  ('transportasi-travel', 'Transportasi & Travel', 8),
  ('keuangan', 'Keuangan', 9),
  ('hiburan', 'Hiburan', 10),
  ('pendidikan-mahasiswa', 'Pendidikan & Mahasiswa', 11),
  ('pulsa-data-tagihan', 'Pulsa, Data & Tagihan', 12)
ON CONFLICT (slug) DO NOTHING;
