-- 0008_enable_azko — Fase 1 AZKO: aktifkan sumber AZKO + seed brand AZKO.
UPDATE sources
SET status = 'aktif', enabled = TRUE
WHERE source_id = 'azko';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('AZKO', 'azko', 'rumah-perabot', 'https://azko.id/promo')
ON CONFLICT (slug) DO NOTHING;
