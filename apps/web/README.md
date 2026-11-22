# @burupromo/web

Next.js App Router + TypeScript strict (ARCHITECTURE.md §3.1, §9).

- Halaman depan = langsung search bar + hasil, **bukan hero**.
- Design token di `packages/ui` (kertas #F6F3EC, tinta #151515, merah #E4572E,
  kuning #FFD23F, hijau #1F7A4C). Larangan: gradien ungu-biru, glassmorphism, blob.
- Search memanggil API sendiri (`NEXT_PUBLIC_API_URL`), bukan Meilisearch langsung.
- PWA: `public/manifest.webmanifest` sudah berisi Share Target (Fase 1).
- Fase 0: halaman menampilkan empty state yang jujur — tidak ada promo palsu.

Jalankan: `pnpm --filter @burupromo/web dev` (butuh API di :3001, atau tampilkan empty state).
