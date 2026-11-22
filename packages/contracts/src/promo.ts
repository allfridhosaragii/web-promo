import { z } from "zod";
// Kontrak /v1 — ARCHITECTURE.md §16. Sumber kebenaran tipe bersama (API <-> Web <-> Ingest).
export const PromoType = z.enum([
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
// A4: lifecycle (dihitung dari tanggal) & moderation (diputuskan manusia)
// adalah DUA field terpisah. Enum tunggal PromoStatus lama DIHAPUS.
export const PromoLifecycle = z.enum([
  "dijadwalkan",
  "aktif",
  "segera_berakhir",
  "kedaluwarsa",
]);
export const PromoModeration = z.enum([
  "belum_ditinjau",
  "terverifikasi",
  "dilaporkan",
  "ditolak",
]);
export const RegionScope = z.enum([
  "nasional",
  "provinsi",
  "kota",
  "outlet_tertentu",
]);
export const Channel = z.enum(["online", "offline", "keduanya"]);

export const BrandSummary = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  logo_url: z.string().url().nullable(),
});
export const PromoSummary = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  summary: z.string(),
  brand: BrandSummary,
  platform: z.string(),
  promo_type: PromoType,
  value_percent: z.number().nullable(),
  value_amount: z.number().nullable(),
  max_discount: z.number().nullable(),
  min_purchase: z.number().nullable(),
  voucher_code: z.string().nullable(),
  channel: Channel,
  category_slugs: z.array(z.string()),
  region_scope: RegionScope,
  region_codes: z.array(z.string()),
  starts_at: z.string().datetime(),
  // A5: ends_at boleh null = "Tanpa batas waktu". is_open_ended = ends_at === null.
  ends_at: z.string().datetime().nullable(),
  is_open_ended: z.boolean(),
  lifecycle: PromoLifecycle,
  moderation: PromoModeration,
  last_confirmed_at: z.string().datetime().nullable(),
  confidence: z.number().min(0).max(1),
  votes_valid: z.number().int().nonnegative(),
  votes_invalid: z.number().int().nonnegative(),
  saves: z.number().int().nonnegative(),
  source_url: z.string().url(),
  evidence_image_url: z.string().url().nullable(),
});
export type PromoSummary = z.infer<typeof PromoSummary>;

export const PromoDetail = PromoSummary.extend({
  how_to_claim: z.string().nullable(),
  requirements: z.array(z.string()),
  payment_methods: z.array(z.string()),
  outlets: z.array(
    z.object({
      id: z.string().uuid(),
      name: z.string(),
      address: z.string().nullable(),
      region_code: z.string(),
      lat: z.number().nullable(),
      lon: z.number().nullable(),
    }),
  ),
  source: z.object({
    id: z.string().uuid(),
    name: z.string(),
    type: z.string(),
  }),
  last_checked_at: z.string().datetime().nullable(),
});
export type PromoDetail = z.infer<typeof PromoDetail>;

export const PromoListQuery = z.object({
  q: z.string().optional(),
  category: z.string().optional(),
  region: z.string().optional(),
  cluster: z.string().optional(),
  brand: z.string().optional(),
  platform: z.string().optional(),
  promo_type: PromoType.optional(),
  channel: Channel.optional(),
  payment: z.string().optional(),
  ends_today: z.coerce.boolean().optional(),
  ends_soon: z.coerce.boolean().optional(),
  no_min_purchase: z.coerce.boolean().optional(),
  student_only: z.coerce.boolean().optional(),
  sort: z
    .enum([
      "relevance",
      "newest",
      "ending_soon",
      "biggest_discount",
      "most_trusted",
      "nearest",
    ])
    .default("relevance"),
  lat: z.coerce.number().optional(),
  lon: z.coerce.number().optional(),
  radius_km: z.coerce.number().optional(),
  page: z.coerce.number().int().min(1).default(1),
  per_page: z.coerce.number().int().min(1).max(50).default(20),
});
export type PromoListQuery = z.infer<typeof PromoListQuery>;

export const VoteBody = z.object({ vote: z.enum(["valid", "invalid"]) });
export const ReportBody = z.object({
  reason: z.enum(["kode_tidak_bisa", "kuota_habis", "palsu", "lainnya"]),
  note: z.string().max(500).optional(),
});
export const SubmissionBody = z.object({
  source_url: z.string().url(),
  title: z.string().optional(),
  note: z.string().max(500).optional(),
  photo_url: z.string().url().nullable().optional(),
});
export const WalletBody = z.object({
  banks: z.array(z.string()),
  ewallets: z.array(z.string()),
});
export const ApiError = z.object({
  error: z.object({ code: z.string(), message: z.string() }),
});
