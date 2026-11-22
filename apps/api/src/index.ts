import { Hono } from "hono";
import { initSentry } from "./lib/sentry";
import { admin } from "./routes/admin";
import { promos } from "./routes/promos";

// Sentry Developer (free tier, Rp0) — DSN dari env, sampling rendah, replay mati.
// Tanpa SENTRY_DSN, initSentry() no-op (lihat lib/sentry.ts).
initSentry();
const app = new Hono();
app.get("/health", (c) =>
  c.json({ ok: true, app: "BuruPromo", phase: "0-skeleton" }),
);
app.route("/v1/promos", promos);
app.route("/admin", admin);
app.get("/v1/regions", (c) =>
  c.json({
    data: [],
    meta: {
      note: "Seed wilayah Jawa Timur tersedia di packages/db — endpoint ini diisi saat DB terhubung (vertical slice).",
    },
  }),
);
app.get("/v1/categories", (c) =>
  c.json({
    data: [],
    meta: {
      note: "Taksonomi di ARCHITECTURE.md §6 — diisi dari DB di Fase 1.",
    },
  }),
);
app.get("/v1/brands", (c) =>
  c.json({ data: [], meta: { note: "Diisi dari DB di Fase 1." } }),
);
app.get("/v1/sources", (c) =>
  c.json({
    data: [],
    meta: {
      note: "Semua konektor disabled di Fase 0 — lihat packages/db/migrations/0001_init.sql.",
    },
  }),
);
app.notFound((c) =>
  c.json(
    { error: { code: "NOT_FOUND", message: "Endpoint tidak ditemukan." } },
    404,
  ),
);
const port = Number(process.env.API_PORT ?? 3001);
console.log(`BuruPromo API (Fase 0 skeleton) mendengarkan di :${port}`);
export default { port, fetch: app.fetch };

// Bootstrap Node: jalankan server saat file dieksekusi langsung (tsx / node).
// Tanpa ini, `pnpm dev` di Docker hanya mengeksekusi modul lalu keluar.
import { serve } from "@hono/node-server";
const entrypoint = process.argv[1] ?? "";
if (entrypoint.endsWith("index.ts") || entrypoint.endsWith("index.js")) {
  serve({ fetch: app.fetch, port });
}
