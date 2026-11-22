-- 0013_enable_mandiri — Fase 1 Bank Mandiri: aktifkan sumber Mandiri + seed brand Bank Mandiri.
INSERT INTO sources (source_id, name, type, status, enabled, base_url)
VALUES ('mandiri', 'Bank Mandiri', 'public_web', 'aktif', TRUE, 'https://www.mandirikartukredit.com/hot-offer')
ON CONFLICT (source_id) DO UPDATE
SET status = 'aktif', enabled = TRUE;

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('Bank Mandiri', 'mandiri', 'bank-kartu', 'https://www.mandirikartukredit.com/hot-offer')
ON CONFLICT (slug) DO NOTHING;
