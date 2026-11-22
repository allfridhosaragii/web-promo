-- 0006_enable_gopay — Fase 1 GoPay: aktifkan sumber GoPay + seed brand GoPay.
UPDATE sources
SET status = 'aktif', enabled = TRUE
WHERE source_id = 'gopay';

INSERT INTO brands (name, slug, category_slug, website)
VALUES ('GoPay', 'gopay', 'keuangan', 'https://gopay.co.id/promo')
ON CONFLICT (slug) DO NOTHING;
