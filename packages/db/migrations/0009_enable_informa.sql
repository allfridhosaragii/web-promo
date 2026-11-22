-- 0009_enable_informa — Fase 1 Informa: aktifkan sumber Informa + seed brand Informa.
UPDATE sources
SET status = 'aktif', enabled = TRUE
WHERE source_id = 'informa';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('Informa', 'informa', 'rumah-perabot', 'https://informa.co.id/home-promotion')
ON CONFLICT (slug) DO NOTHING;
