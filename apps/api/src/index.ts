import { getPool } from "@burupromo/db";
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { initSentry } from "./lib/sentry";
import { admin } from "./routes/admin";
import { promos } from "./routes/promos";

// Sentry Developer (free tier, Rp0) — DSN dari env, sampling rendah, replay mati.
// Tanpa SENTRY_DSN, initSentry() no-op (lihat lib/sentry.ts).
initSentry();

const app = new Hono();

app.get("/health", (c) =>
  c.json({ ok: true, app: "BuruPromo", phase: "1-vertical-slice-bca" }),
);

app.route("/v1/promos", promos);
app.route("/admin", admin);

app.get("/v1/regions", async (c) => {
  const pool = getPool();
  const res = await pool.query(
    "SELECT code, code_bps, name, level::text, parent_code, cluster FROM regions ORDER BY code",
  );
  return c.json({ data: res.rows });
});

app.get("/v1/categories", async (c) => {
  const pool = getPool();
  const res = await pool.query(
    "SELECT id, slug, name, parent_id, sort_order FROM categories ORDER BY sort_order, name",
  );
  return c.json({ data: res.rows });
});

app.get("/v1/brands", async (c) => {
  const pool = getPool();
  const res = await pool.query(
    "SELECT id, name, slug, logo_url, category_slug, website FROM brands ORDER BY name",
  );
  return c.json({ data: res.rows });
});

app.get("/v1/sources", async (c) => {
  const pool = getPool();
  const res = await pool.query(
    `SELECT source_id, name, type::text, status, enabled, base_url,
            last_success_at, last_error, last_latency_ms
     FROM sources
     ORDER BY source_id`,
  );
  return c.json({ data: res.rows });
});

app.notFound((c) =>
  c.json(
    { error: { code: "NOT_FOUND", message: "Endpoint tidak ditemukan." } },
    404,
  ),
);

const port = Number(process.env.API_PORT ?? 3001);
console.log(`BuruPromo API mendengarkan di :${port}`);
export default { port, fetch: app.fetch };

// Bootstrap Node: jalankan server saat file dieksekusi langsung (tsx / node).
const entrypoint = process.argv[1] ?? "";
if (entrypoint.endsWith("index.ts") || entrypoint.endsWith("index.js")) {
  serve({ fetch: app.fetch, port });
}
