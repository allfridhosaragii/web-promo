-- 0010_enable_cimb — Fase 1 CIMB Niaga: aktifkan sumber CIMB + seed brand CIMB Niaga.
INSERT INTO sources (source_id, name, type, status, enabled, base_url)
VALUES ('cimb', 'CIMB Niaga', 'public_web', 'aktif', TRUE, 'https://www.cimbniaga.co.id/id/personal/promo')
ON CONFLICT (source_id) DO UPDATE
SET status = 'aktif', enabled = TRUE;

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('CIMB Niaga', 'cimb-niaga', 'bank-kartu', 'https://www.cimbniaga.co.id/id/personal/promo')
ON CONFLICT (slug) DO NOTHING;
