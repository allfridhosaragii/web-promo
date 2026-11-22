-- 0012_enable_indomaret — Fase 1 Indomaret: aktifkan sumber Indomaret + seed brand Indomaret.
INSERT INTO sources (source_id, name, type, status, enabled, base_url)
VALUES ('indomaret', 'Indomaret', 'public_web', 'aktif', TRUE, 'https://www.indomaret.co.id/promosi/')
ON CONFLICT (source_id) DO UPDATE
SET status = 'aktif', enabled = TRUE;

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('Indomaret', 'indomaret', 'minimarket', 'https://www.indomaret.co.id/promosi/')
ON CONFLICT (slug) DO NOTHING;
