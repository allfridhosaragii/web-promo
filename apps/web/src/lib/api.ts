import type { PromoSummary } from "@burupromo/contracts";
import { API_URL } from "./constants";
export type PromoListResponse = {
  data: PromoSummary[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
};
/** Fase 0: API belum punya data nyata — kembalikan list kosong, jangan tampilkan promo palsu. */
export async function fetchPromos(
  params: Record<string, string> = {},
): Promise<PromoListResponse> {
  const qs = new URLSearchParams(params);
  const res = await fetch(`${API_URL}/v1/promos?${qs.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok)
    return {
      data: [],
      meta: { page: 1, per_page: 20, total: 0, total_pages: 0 },
    };
  return (await res.json()) as PromoListResponse;
}
