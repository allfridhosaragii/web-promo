import { Hono } from "hono";

// Admin — Fase 0 stub yang jujur (ARCH §16.5, §11.1, §17).
// GET /admin/stats menampilkan kuota LLM hari ini + antrean + status sinkron
// Spreadsheet terakhir. Angka di sini placeholder sampai worker ingest
// menulis status nyata ke Redis/Postgres (vertical slice BCA).
// Auth peran admin/moderator diaktifkan di Fase 1 (Better Auth) — endpoint
// ini belum dipakai produksi dan mengembalikan 501 bila dipanggil tanpa
// konteks admin yang sesungguhnya. Untuk sekarang: kembalikan status skeleton.
export const admin = new Hono();

admin.get("/stats", (c) =>
  c.json({
    data: {
      llm: {
        provider: "gemini",
        // Model TIDAK dikunci di kode — diisi owner dari AI Studio (ARCH §11.1).
        model: process.env.LLM_MODEL ? "(terisi dari .env)" : null,
        billing: "none — free tier, tanpa billing account",
        daily_limit_requests: Number(process.env.LLM_DAILY_REQUEST_LIMIT ?? 20),
        rpm_limit: Number(process.env.LLM_RPM ?? 10),
        used_today: null,
        remaining_today: null,
        reset_at_pt: "00:00 America/Los_Angeles",
        queued_llm: null,
        note: "Status kuota nyata diisi worker ingest (QuotaGuard.status) di vertical slice BCA.",
      },
      sheets_sync: {
        enabled: Boolean(process.env.GOOGLE_SHEETS_SPREADSHEET_ID),
        spreadsheet_id: process.env.GOOGLE_SHEETS_SPREADSHEET_ID
          ? "(terisi)"
          : null,
        queued_sheets: null,
        last_success_at: null,
        last_error: null,
        note: "Status sinkron nyata diisi worker ingest (SheetsSync.status + tabel sync_log) di vertical slice BCA.",
      },
      vm: {
        hosting: "Oracle Cloud Always Free (rencana) — Fase 0 jalan lokal",
        note: "Status VM (CPU/RAM/disk) + sisa jatah Oracle diinput manual dari console.",
      },
    },
    meta: { phase: "0-skeleton" },
  }),
);

admin.get("/sources", (c) =>
  c.json({
    data: [],
    meta: {
      note: "Semua konektor disabled di Fase 0 — kill switch aktif di vertical slice.",
    },
  }),
);
