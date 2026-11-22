-- 0011_enable_ovo — Fase 1 OVO: aktifkan sumber OVO + seed brand OVO.
UPDATE sources
SET status = 'aktif', enabled = TRUE
WHERE source_id = 'ovo';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('OVO', 'ovo', 'ewallet', 'https://ovo.id/deals')
ON CONFLICT (slug) DO NOTHING;
