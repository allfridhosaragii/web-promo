import { defineConfig } from "tsup";

// Bundel paket workspace @burupromo/* ke dalam dist/index.js.
// Tanpa noExternal, tsup menganggap paket workspace sebagai dependensi
// eksternal (symlink node_modules) dan Node runtime gagal memuat .ts mentah
// (ERR_MODULE_NOT_FOUND './promo' tanpa ekstensi). Dependensi npm asli
// (hono, drizzle-orm, pg, @sentry/node) tetap eksternal — tersedia di
// node_modules image produksi.
export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  outDir: "dist",
  clean: true,
  noExternal: [/^@burupromo\//],
});
