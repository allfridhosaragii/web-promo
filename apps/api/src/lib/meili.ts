export interface MeiliSearchResponse {
  hits: Array<{ id: string }>;
  estimatedTotalHits?: number;
}

export async function searchMeilisearch(params: {
  q?: string | undefined;
  filter: string[];
  sort?: string[] | undefined;
  page: number;
  perPage: number;
}): Promise<MeiliSearchResponse | null> {
  const host = process.env.MEILISEARCH_HOST?.replace(/\/$/, "");
  if (!host) return null;
  const index = process.env.MEILISEARCH_INDEX_PROMOS ?? "promos";
  const key = process.env.MEILISEARCH_MASTER_KEY;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (key) headers.Authorization = `Bearer ${key}`;

  try {
    const res = await fetch(`${host}/indexes/${index}/search`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        q: params.q ?? "",
        filter: params.filter,
        sort: params.sort,
        page: params.page,
        hitsPerPage: params.perPage,
        attributesToRetrieve: ["id"],
      }),
    });
    if (!res.ok) return null;
    return (await res.json()) as MeiliSearchResponse;
  } catch {
    return null;
  }
}
