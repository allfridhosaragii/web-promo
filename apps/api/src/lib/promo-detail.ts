import type { PromoDetail } from "@burupromo/contracts";

// Aturan GET /v1/promos/{id} (ARCH §16.1, perbaikan A6):
// - id tidak ada -> 404.
// - moderation = ditolak -> 404 (promo ditolak tidak ditampilkan).
// - lifecycle = kedaluwarsa -> 200 + lifecycle "kedaluwarsa" (arsip, bukan 404).
//   Web menampilkan "Promo sudah berakhir" + promo serupa + meta noindex.
// - lifecycle lainnya -> 200.
export type DetailLookup =
  | { status: 200; promo: PromoDetail }
  | { status: 404; code: "NOT_FOUND" };

export function resolvePromoDetail(promo: PromoDetail | null): DetailLookup {
  if (promo === null) return { status: 404, code: "NOT_FOUND" };
  if (promo.moderation === "ditolak") return { status: 404, code: "NOT_FOUND" };
  return { status: 200, promo };
}
