import {
  type PromoDetail,
  PromoListQuery,
  type PromoSummary,
} from "@burupromo/contracts";
import { getPool } from "@burupromo/db";
import { Hono } from "hono";
import { searchMeilisearch } from "../lib/meili";
import { resolvePromoDetail } from "../lib/promo-detail";

export const promos = new Hono();

interface PromoRow {
  id: string;
  title: string;
  summary: string;
  brand_id: string | null;
  brand_name: string | null;
  brand_slug: string | null;
  brand_logo_url: string | null;
  platform: string | null;
  promo_type: PromoSummary["promo_type"];
  value_percent: number | null;
  value_amount: number | null;
  max_discount: number | null;
  min_purchase: number | null;
  voucher_code: string | null;
  how_to_claim: string | null;
  payment_methods: string[] | null;
  requirements: string[] | null;
  channel: PromoSummary["channel"];
  category_ids: string[] | null;
  region_scope: PromoSummary["region_scope"];
  region_codes: string[] | null;
  starts_at: Date;
  ends_at: Date | null;
  lifecycle: PromoSummary["lifecycle"];
  moderation: PromoSummary["moderation"];
  last_confirmed_at: Date | null;
  last_checked_at: Date | null;
  confidence: number;
  votes_valid: number;
  votes_invalid: number;
  saves: number;
  source_url: string;
  evidence_image_url: string | null;
  source_uuid: string | null;
  source_name: string | null;
  source_type: string | null;
}

const FALLBACK_BRAND_ID = "00000000-0000-0000-0000-000000000000";

function mapRowToSummary(
  row: PromoRow,
  categoryMap: Map<string, string>,
): PromoSummary {
  const catIds = Array.isArray(row.category_ids) ? row.category_ids : [];
  const categorySlugs = catIds
    .map((id) => categoryMap.get(id))
    .filter((s): s is string => Boolean(s));

  return {
    id: row.id,
    title: row.title,
    summary: row.summary,
    brand: {
      id: row.brand_id ?? FALLBACK_BRAND_ID,
      name: row.brand_name ?? row.platform ?? "BCA",
      slug: row.brand_slug ?? "bca",
      logo_url: row.brand_logo_url ?? null,
    },
    platform: row.platform ?? "BCA",
    promo_type: row.promo_type,
    value_percent: row.value_percent,
    value_amount: row.value_amount,
    max_discount: row.max_discount,
    min_purchase: row.min_purchase,
    voucher_code: row.voucher_code,
    channel: row.channel,
    category_slugs: categorySlugs,
    region_scope: row.region_scope,
    region_codes: Array.isArray(row.region_codes) ? row.region_codes : [],
    starts_at: new Date(row.starts_at).toISOString(),
    ends_at: row.ends_at ? new Date(row.ends_at).toISOString() : null,
    is_open_ended: row.ends_at === null,
    lifecycle: row.lifecycle,
    moderation: row.moderation,
    last_confirmed_at: row.last_confirmed_at
      ? new Date(row.last_confirmed_at).toISOString()
      : null,
    confidence: Number(row.confidence ?? 0.5),
    votes_valid: row.votes_valid ?? 0,
    votes_invalid: row.votes_invalid ?? 0,
    saves: row.saves ?? 0,
    source_url: row.source_url,
    evidence_image_url: row.evidence_image_url,
  };
}

async function getCategorySlugMap(): Promise<Map<string, string>> {
  const pool = getPool();
  const res = await pool.query<{ id: string; slug: string }>(
    "SELECT id, slug FROM categories",
  );
  return new Map(res.rows.map((r) => [r.id, r.slug]));
}

promos.get("/", async (c) => {
  const parsed = PromoListQuery.safeParse(c.req.query());
  if (!parsed.success) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: parsed.error.message } },
      400,
    );
  }
  const q = parsed.data;
  const pool = getPool();
  const categoryMap = await getCategorySlugMap();

  // Coba Meilisearch dulu bila ada query teks `q`
  if (q.q?.trim()) {
    const filters = [
      'lifecycle IN ["aktif", "segera_berakhir"]',
      'moderation != "ditolak"',
      "is_seed = false",
    ];
    if (q.brand) filters.push(`brand_slug = "${q.brand}"`);
    if (q.platform) filters.push(`platform = "${q.platform}"`);
    if (q.promo_type) filters.push(`promo_type = "${q.promo_type}"`);
    if (q.channel) filters.push(`channel = "${q.channel}"`);
    if (q.category) filters.push(`category_slugs = "${q.category}"`);
    if (q.payment) filters.push(`payment_methods = "${q.payment}"`);
    if (q.no_min_purchase) filters.push("min_purchase IS NULL");

    const sortMap: Record<string, string[]> = {
      newest: ["created_at:desc"],
      ending_soon: ["ends_at_ts:asc"],
      biggest_discount: ["value_percent:desc", "value_amount:desc"],
      most_trusted: ["confidence:desc", "votes_valid:desc"],
    };

    const meili = await searchMeilisearch({
      q: q.q,
      filter: filters,
      sort: sortMap[q.sort],
      page: q.page,
      perPage: q.per_page,
    });

    if (meili && meili.hits.length > 0) {
      const ids = meili.hits.map((h) => h.id);
      const rowsRes = await pool.query<PromoRow>(
        `SELECT p.*, b.name AS brand_name, b.slug AS brand_slug, b.logo_url AS brand_logo_url
         FROM promos p
         LEFT JOIN brands b ON b.id = p.brand_id
         WHERE p.id = ANY($1::uuid[])
           AND p.lifecycle IN ('aktif', 'segera_berakhir')
           AND p.moderation != 'ditolak'
           AND p.is_seed = FALSE`,
        [ids],
      );
      const byId = new Map(rowsRes.rows.map((r) => [r.id, r]));
      const ordered = ids
        .map((id) => byId.get(id))
        .filter((r): r is PromoRow => Boolean(r))
        .map((r) => mapRowToSummary(r, categoryMap));
      const total = meili.estimatedTotalHits ?? ordered.length;
      return c.json({
        data: ordered,
        meta: {
          page: q.page,
          per_page: q.per_page,
          total,
          total_pages: Math.ceil(total / q.per_page),
        },
      });
    }
  }

  // Fallback / query langsung ke Postgres
  const where: string[] = [
    "p.lifecycle IN ('aktif', 'segera_berakhir')",
    "p.moderation != 'ditolak'",
    "p.is_seed = FALSE",
  ];
  const values: unknown[] = [];

  if (q.q?.trim()) {
    values.push(`%${q.q.trim()}%`);
    const idx = values.length;
    where.push(
      `(p.title ILIKE $${idx} OR p.summary ILIKE $${idx} OR p.platform ILIKE $${idx} OR b.name ILIKE $${idx})`,
    );
  }
  if (q.brand) {
    values.push(q.brand);
    where.push(`b.slug = $${values.length}`);
  }
  if (q.platform) {
    values.push(q.platform);
    where.push(`LOWER(p.platform) = LOWER($${values.length})`);
  }
  if (q.promo_type) {
    values.push(q.promo_type);
    where.push(`p.promo_type = $${values.length}`);
  }
  if (q.channel) {
    values.push(q.channel);
    where.push(`p.channel = $${values.length}`);
  }
  if (q.no_min_purchase) {
    where.push("p.min_purchase IS NULL");
  }
  if (q.ends_soon) {
    where.push("p.lifecycle = 'segera_berakhir'");
  }
  if (q.category) {
    const catId = [...categoryMap.entries()].find(
      ([, slug]) => slug === q.category,
    )?.[0];
    if (catId) {
      values.push(JSON.stringify([catId]));
      where.push(`p.category_ids @> $${values.length}::jsonb`);
    } else {
      where.push("FALSE");
    }
  }

  const orderSql =
    q.sort === "ending_soon"
      ? "p.ends_at ASC NULLS LAST"
      : q.sort === "biggest_discount"
        ? "COALESCE(p.value_percent, 0) DESC, COALESCE(p.value_amount, 0) DESC"
        : q.sort === "most_trusted"
          ? "p.confidence DESC, p.votes_valid DESC"
          : "p.created_at DESC";

  const whereSql = where.join(" AND ");
  const countRes = await pool.query<{ cnt: string }>(
    `SELECT COUNT(*)::text AS cnt
     FROM promos p
     LEFT JOIN brands b ON b.id = p.brand_id
     WHERE ${whereSql}`,
    values,
  );
  const total = Number(countRes.rows[0]?.cnt ?? 0);

  const offset = (q.page - 1) * q.per_page;
  values.push(q.per_page, offset);
  const limitIdx = values.length - 1;
  const offsetIdx = values.length;

  const rowsRes = await pool.query<PromoRow>(
    `SELECT p.*, b.name AS brand_name, b.slug AS brand_slug, b.logo_url AS brand_logo_url
     FROM promos p
     LEFT JOIN brands b ON b.id = p.brand_id
     WHERE ${whereSql}
     ORDER BY ${orderSql}
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    values,
  );

  return c.json({
    data: rowsRes.rows.map((r) => mapRowToSummary(r, categoryMap)),
    meta: {
      page: q.page,
      per_page: q.per_page,
      total,
      total_pages: total === 0 ? 0 : Math.ceil(total / q.per_page),
    },
  });
});

promos.get("/:id", async (c) => {
  const id = c.req.param("id");
  const uuidRe =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuidRe.test(id)) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Promo tidak ditemukan." } },
      404,
    );
  }

  const pool = getPool();
  const res = await pool.query<PromoRow>(
    `SELECT p.*,
            b.name AS brand_name, b.slug AS brand_slug, b.logo_url AS brand_logo_url,
            s.id AS source_uuid, s.name AS source_name, s.type::text AS source_type
     FROM promos p
     LEFT JOIN brands b ON b.id = p.brand_id
     LEFT JOIN sources s ON s.source_id = p.source_id
     WHERE p.id = $1::uuid`,
    [id],
  );
  const row = res.rows[0];
  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Promo tidak ditemukan." } },
      404,
    );
  }

  const categoryMap = await getCategorySlugMap();
  const summary = mapRowToSummary(row, categoryMap);
  const detail: PromoDetail = {
    ...summary,
    how_to_claim: row.how_to_claim,
    requirements: Array.isArray(row.requirements) ? row.requirements : [],
    payment_methods: Array.isArray(row.payment_methods)
      ? row.payment_methods
      : [],
    outlets: [],
    source: {
      id: row.source_uuid ?? FALLBACK_BRAND_ID,
      name: row.source_name ?? "BCA",
      type: row.source_type ?? "public_web",
    },
    last_checked_at: row.last_checked_at
      ? new Date(row.last_checked_at).toISOString()
      : null,
  };

  const lookup = resolvePromoDetail(detail);
  if (lookup.status === 404) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Promo tidak ditemukan." } },
      404,
    );
  }
  return c.json(lookup.promo);
});

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
