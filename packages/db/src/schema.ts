// Drizzle schema — ARCHITECTURE.md §4. Semua *_at disimpan UTC, ditampilkan WIB.
import { sql } from "drizzle-orm";
import {
  boolean,
  doublePrecision,
  index,
  integer,
  jsonb,
  pgEnum,
  pgTable,
  real,
  text,
  timestamp,
  uniqueIndex,
  uuid,
  varchar,
} from "drizzle-orm/pg-core";

export const regionLevel = pgEnum("region_level", [
  "provinsi",
  "kab_kota",
  "kecamatan",
]);
export const promoType = pgEnum("promo_type", [
  "persen",
  "potongan_nominal",
  "cashback",
  "beli_x_gratis_y",
  "gratis_ongkir",
  "harga_spesial",
  "bundling",
  "poin",
  "cicilan_0",
  "lainnya",
]);
// A4 (perbaikan status): lifecycle & moderation adalah DUA kolom terpisah.
// lifecycle dihitung dari tanggal (pipeline/expire.py compute_lifecycle).
// moderation diputuskan manusia/komunitas, bukan dari tanggal.
// Index utama Meilisearch: lifecycle IN (aktif, segera_berakhir)
// AND moderation != ditolak (lihat pipeline/index.py should_index).
export const promoLifecycle = pgEnum("promo_lifecycle", [
  "dijadwalkan",
  "aktif",
  "segera_berakhir",
  "kedaluwarsa",
]);
export const promoModeration = pgEnum("promo_moderation", [
  "belum_ditinjau",
  "terverifikasi",
  "dilaporkan",
  "ditolak",
]);
export const regionScope = pgEnum("region_scope", [
  "nasional",
  "provinsi",
  "kota",
  "outlet_tertentu",
]);
export const channel = pgEnum("channel", ["online", "offline", "keduanya"]);
export const sourceType = pgEnum("source_type", [
  "official_api",
  "public_web",
  "affiliate_feed",
  "community",
  "disabled",
]);
export const userRole = pgEnum("user_role", ["user", "moderator", "admin"]);

export const regions = pgTable(
  "regions",
  {
    code: varchar("code", { length: 20 }).primaryKey(), // code_dagri, mis. 35.78
    codeBps: varchar("code_bps", { length: 20 }),
    name: text("name").notNull(),
    level: regionLevel("level").notNull(),
    parentCode: varchar("parent_code", { length: 20 }),
    cluster: varchar("cluster", { length: 100 }),
    // PostGIS MULTIPOLYGON SRID 4326. Fase 0: boleh NULL — lihat seed/wilayah/MANIFEST.md.
    geom: text("geom"),
  },
  (t) => [
    index("regions_parent_idx").on(t.parentCode),
    index("regions_cluster_idx").on(t.cluster),
  ],
);

export const regionClusters = pgTable("region_clusters", {
  id: uuid("id").defaultRandom().primaryKey(),
  slug: varchar("slug", { length: 100 }).notNull().unique(),
  name: text("name").notNull(),
  provinceCode: varchar("province_code", { length: 20 }).notNull(),
});

export const categories = pgTable("categories", {
  id: uuid("id").defaultRandom().primaryKey(),
  slug: varchar("slug", { length: 100 }).notNull().unique(),
  name: text("name").notNull(),
  parentId: uuid("parent_id"),
  sortOrder: integer("sort_order").default(0).notNull(),
});

export const brands = pgTable("brands", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull(),
  slug: varchar("slug", { length: 100 }).notNull().unique(),
  logoUrl: text("logo_url"),
  categorySlug: varchar("category_slug", { length: 100 }),
  website: text("website"),
  socialHandles: jsonb("social_handles")
    .$type<Record<string, string>>()
    .default({}),
});

export const outlets = pgTable(
  "outlets",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    brandId: uuid("brand_id")
      .notNull()
      .references(() => brands.id),
    name: text("name").notNull(),
    address: text("address"),
    regionCode: varchar("region_code", { length: 20 }).notNull(),
    lat: doublePrecision("lat"),
    lon: doublePrecision("lon"),
  },
  (t) => [
    index("outlets_brand_idx").on(t.brandId),
    index("outlets_region_idx").on(t.regionCode),
  ],
);

export const sources = pgTable("sources", {
  id: uuid("id").defaultRandom().primaryKey(),
  sourceId: varchar("source_id", { length: 100 }).notNull().unique(), // mis. "bca"
  name: text("name").notNull(),
  type: sourceType("type").notNull(),
  status: varchar("status", { length: 20 }).notNull().default("disabled"), // aktif | paused | disabled
  enabled: boolean("enabled").notNull().default(false),
  scheduleCron: varchar("schedule_cron", { length: 50 }).default("0 */6 * * *"),
  budgetDailyUsd: real("budget_daily_usd").default(0).notNull(),
  baseUrl: text("base_url"),
  lastSuccessAt: timestamp("last_success_at", { withTimezone: true }),
  lastError: text("last_error"),
  lastLatencyMs: integer("last_latency_ms"),
});

export const rawItems = pgTable(
  "raw_items",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    sourceId: varchar("source_id", { length: 100 }).notNull(),
    sourceUrl: text("source_url").notNull(),
    title: text("title"),
    text: text("text").notNull(),
    html: text("html"),
    mediaUrls: jsonb("media_urls").$type<string[]>().default([]),
    contentHash: varchar("content_hash", { length: 64 }),
    fetchedAt: timestamp("fetched_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (t) => [
    index("raw_items_source_idx").on(t.sourceId),
    index("raw_items_fetched_idx").on(t.fetchedAt),
    uniqueIndex("raw_items_hash_idx").on(t.contentHash),
  ],
);

export const promos = pgTable(
  "promos",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    title: text("title").notNull(),
    summary: text("summary").notNull(),
    promoType: promoType("promo_type").notNull(),
    valuePercent: real("value_percent"),
    valueAmount: integer("value_amount"),
    maxDiscount: integer("max_discount"),
    minPurchase: integer("min_purchase"),
    voucherCode: varchar("voucher_code", { length: 100 }),
    howToClaim: text("how_to_claim"),
    paymentMethods: jsonb("payment_methods").$type<string[]>().default([]),
    requirements: jsonb("requirements").$type<string[]>().default([]),
    channel: channel("channel").notNull().default("online"),
    platform: varchar("platform", { length: 100 }),
    categoryIds: jsonb("category_ids").$type<string[]>().default([]),
    brandId: uuid("brand_id").references(() => brands.id),
    regionScope: regionScope("region_scope").notNull().default("nasional"),
    regionCodes: jsonb("region_codes").$type<string[]>().default([]),
    startsAt: timestamp("starts_at", { withTimezone: true }),
    endsAt: timestamp("ends_at", { withTimezone: true }),
    recurringRule: varchar("recurring_rule", { length: 200 }),
    recurrenceEnd: timestamp("recurrence_end", { withTimezone: true }),
    quotaNote: text("quota_note"),
    sourceId: varchar("source_id", { length: 100 }).notNull(),
    sourceUrl: text("source_url").notNull(),
    evidenceImageUrl: text("evidence_image_url"),
    confidence: real("confidence").notNull().default(0.5),
    lifecycle: promoLifecycle("lifecycle").notNull().default("dijadwalkan"),
    moderation: promoModeration("moderation")
      .notNull()
      .default("belum_ditinjau"),
    lastCheckedAt: timestamp("last_checked_at", { withTimezone: true }),
    // A5: promo tanpa ends_at ("Tanpa batas waktu") wajib recheck tiap 6 jam;
    // auto-kedaluwarsa bila tidak terkonfirmasi selama 14 hari.
    lastConfirmedAt: timestamp("last_confirmed_at", { withTimezone: true }),
    votesValid: integer("votes_valid").notNull().default(0),
    votesInvalid: integer("votes_invalid").notNull().default(0),
    views: integer("views").notNull().default(0),
    saves: integer("saves").notNull().default(0),
    dedupKey: varchar("dedup_key", { length: 200 }),
    embedding: text("embedding"), // pgvector vector(768) — diaktifkan via migrasi saat pgvector tersedia
    isSeed: boolean("is_seed").notNull().default(false), // dummy dev: TIDAK masuk index produksi
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (t) => [
    index("promos_lifecycle_idx").on(t.lifecycle),
    index("promos_moderation_idx").on(t.moderation),
    index("promos_ends_at_idx").on(t.endsAt),
    index("promos_brand_idx").on(t.brandId),
    index("promos_source_idx").on(t.sourceId),
    uniqueIndex("promos_dedup_idx").on(t.dedupKey),
  ],
);

export const users = pgTable("users", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  name: text("name"),
  role: userRole("role").notNull().default("user"),
  reputation: integer("reputation").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});
export const savedPromos = pgTable(
  "saved_promos",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    promoId: uuid("promo_id")
      .notNull()
      .references(() => promos.id),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (t) => [uniqueIndex("saved_promos_uq").on(t.userId, t.promoId)],
);
export const savedSearches = pgTable("saved_searches", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id),
  query: text("query"),
  categorySlug: varchar("category_slug", { length: 100 }),
  regionCode: varchar("region_code", { length: 20 }),
  notifyVia: jsonb("notify_via").$type<string[]>().default([]),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});
export const walletPreferences = pgTable("wallet_preferences", {
  userId: uuid("user_id")
    .primaryKey()
    .references(() => users.id),
  banks: jsonb("banks").$type<string[]>().default([]),
  ewallets: jsonb("ewallets").$type<string[]>().default([]),
});
export const submissions = pgTable("submissions", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id),
  sourceUrl: text("source_url").notNull(),
  title: text("title"),
  note: text("note"),
  photoUrl: text("photo_url"),
  status: varchar("status", { length: 30 })
    .notNull()
    .default("menunggu_moderasi"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});
export const reports = pgTable("reports", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id),
  promoId: uuid("promo_id")
    .notNull()
    .references(() => promos.id),
  reason: varchar("reason", { length: 50 }).notNull(),
  note: text("note"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});
export const votes = pgTable(
  "votes",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    promoId: uuid("promo_id")
      .notNull()
      .references(() => promos.id),
    vote: varchar("vote", { length: 10 }).notNull(), // valid | invalid
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (t) => [uniqueIndex("votes_uq").on(t.userId, t.promoId)],
);
export const syncAction = pgEnum("sync_action", [
  "upsert",
  "pindah_arsip",
  "hapus",
  "retry",
  "gagal",
]);
export const syncStatus = pgEnum("sync_status", ["ok", "gagal", "antre"]);

// sync_log — audit sinkron Spreadsheet (ARCH §17.5, revisi 2). Sumber kebenaran
// untuk audit sinkron; sheet "Log Sinkron" hanya cerminnya. Kalau Sheets API
// mati, log tetap tercatat di sini (sheet tidak bisa ditulis saat API down).
export const syncLog = pgTable(
  "sync_log",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    promoId: uuid("promo_id").references(() => promos.id),
    sheet: varchar("sheet", { length: 50 }).notNull(), // Promo Aktif | Arsip | Log Sinkron
    action: syncAction("action").notNull(),
    status: syncStatus("status").notNull(),
    error: text("error"),
    attemptedAt: timestamp("attempted_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
  },
  (t) => [
    index("sync_log_promo_idx").on(t.promoId),
    index("sync_log_attempted_idx").on(t.attemptedAt),
  ],
);

export const moderationLog = pgTable("moderation_log", {
  id: uuid("id").defaultRandom().primaryKey(),
  actorId: uuid("actor_id").references(() => users.id),
  action: varchar("action", { length: 50 }).notNull(),
  targetType: varchar("target_type", { length: 50 }).notNull(),
  targetId: uuid("target_id"),
  note: text("note"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});
export const promoSources = pgTable(
  "promo_sources",
  {
    promoId: uuid("promo_id")
      .notNull()
      .references(() => promos.id),
    sourceId: varchar("source_id", { length: 100 }).notNull(),
    sourceUrl: text("source_url").notNull(),
  },
  (t) => [uniqueIndex("promo_sources_uq").on(t.promoId, t.sourceId)],
);
