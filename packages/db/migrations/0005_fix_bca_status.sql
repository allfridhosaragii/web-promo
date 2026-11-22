-- 0005_fix_bca_status — Perbaiki kosakata status sumber BCA ('aktif', bukan 'public_web').
UPDATE sources
SET status = 'aktif'
WHERE source_id = 'bca';
