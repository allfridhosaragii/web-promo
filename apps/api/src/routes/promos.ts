import { PromoListQuery } from "@burupromo/contracts";
import { Hono } from "hono";
// Fase 0: stub yang jujur — belum ada promo terindeks, kembalikan list kosong.
// Vertical slice BCA akan mengisi ini dari Postgres + Meilisearch.
export const promos = new Hono();
promos.get("/", (c) => {
  const parsed = PromoListQuery.safeParse(c.req.query());
  if (!parsed.success)
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: parsed.error.message } },
      400,
    );
  return c.json({
    data: [],
    meta: {
      page: parsed.data.page,
      per_page: parsed.data.per_page,
      total: 0,
      total_pages: 0,
    },
  });
});
promos.get("/:id", (c) =>
  c.json(
    { error: { code: "NOT_FOUND", message: "Promo tidak ditemukan." } },
    404,
  ),
);
promos.post("/:id/vote", (c) =>
  c.json(
    {
      error: {
        code: "NOT_IMPLEMENTED",
        message: "Voting aktif di Fase 1 (butuh auth).",
      },
    },
    501,
  ),
);
promos.post("/:id/report", (c) =>
  c.json(
    {
      error: {
        code: "NOT_IMPLEMENTED",
        message: "Laporan aktif di Fase 1 (butuh auth).",
      },
    },
    501,
  ),
);
