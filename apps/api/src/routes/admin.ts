import { getPool } from "@burupromo/db";
import { Hono } from "hono";

export const admin = new Hono();

admin.get("/stats", async (c) => {
  const pool = getPool();
  const [counts, lastSync] = await Promise.all([
    pool.query<{ lifecycle: string; cnt: string }>(
      "SELECT lifecycle::text, COUNT(*)::text AS cnt FROM promos WHERE is_seed = FALSE GROUP BY lifecycle",
    ),
    pool.query<{
      synced_at: Date;
      status: string;
      error: string | null;
    }>(
      "SELECT synced_at, status, error FROM sync_log ORDER BY synced_at DESC LIMIT 1",
    ),
  ]);

  const byLifecycle = Object.fromEntries(
    counts.rows.map((r) => [r.lifecycle, Number(r.cnt)]),
  );

  return c.json({
    data: {
      promos: byLifecycle,
      llm: {
        provider: "gemini",
        model: process.env.LLM_MODEL ? "(terisi dari .env)" : null,
        billing: "none — free tier, tanpa billing account",
        daily_limit_requests: Number(process.env.LLM_DAILY_REQUEST_LIMIT ?? 20),
        rpm_limit: Number(process.env.LLM_RPM ?? 10),
        reset_at_pt: "00:00 America/Los_Angeles",
      },
      sheets_sync: {
        enabled: Boolean(process.env.GOOGLE_SHEETS_SPREADSHEET_ID),
        spreadsheet_id: process.env.GOOGLE_SHEETS_SPREADSHEET_ID
          ? "(terisi)"
          : null,
        last_success_at:
          lastSync.rows[0]?.status === "ok"
            ? new Date(lastSync.rows[0].synced_at).toISOString()
            : null,
        last_error: lastSync.rows[0]?.error ?? null,
      },
      vm: {
        hosting: "Oracle Cloud Always Free (rencana) — jalan lokal",
      },
    },
    meta: { phase: "1-vertical-slice-bca" },
  });
});

admin.get("/sources", async (c) => {
  const pool = getPool();
  const res = await pool.query(
    `SELECT source_id, name, type::text, status, enabled, schedule_cron,
            base_url, last_success_at, last_error, last_latency_ms
     FROM sources
     ORDER BY source_id`,
  );
  return c.json({ data: res.rows });
});

admin.post("/sources/:sourceId/toggle", async (c) => {
  const sourceId = c.req.param("sourceId");
  const pool = getPool();
  const res = await pool.query(
    `UPDATE sources
     SET enabled = NOT enabled
     WHERE source_id = $1
     RETURNING source_id, enabled, status`,
    [sourceId],
  );
  if (res.rowCount === 0) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Sumber tidak ditemukan." } },
      404,
    );
  }
  return c.json({ data: res.rows[0] });
});
