-- 0007_enable_bni — Fase 1 BNI (bniexperience): aktifkan sumber BNI + seed brand BNI.
UPDATE sources
SET status = 'aktif', enabled = TRUE
WHERE source_id = 'bni';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('BNI', 'bni', 'keuangan', 'https://bniexperience.bni.co.id/promo')
ON CONFLICT (slug) DO NOTHING;
