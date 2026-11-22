import { revalidatePath, revalidateTag } from "next/cache";
import { handleRevalidate } from "../../../lib/revalidate";

// POST /api/revalidate — dipanggil worker ingest / API setelah promo
// dibuat/diubah/kedaluwarsa (ARCH §17.4, perbaikan F).
// Header: x-revalidate-secret: <REVALIDATE_SECRET dari .env>
// Body: { "paths": ["/", "/promo/<id>"], "tags": ["promos"] } (opsional).
// Secret salah / belum dikonfigurasi -> 401. Tanpa secret, TIDAK ADA
// revalidate yang terjadi (fail closed).
export async function POST(request: Request) {
  let body: { paths?: string[]; tags?: string[] } = {};
  try {
    body = (await request.json()) as typeof body;
  } catch {
    body = {};
  }
  const result = handleRevalidate({
    configuredSecret: process.env.REVALIDATE_SECRET,
    providedSecret: request.headers.get("x-revalidate-secret"),
    paths: body.paths,
    tags: body.tags,
    revalidator: { revalidatePath, revalidateTag },
  });
  if (result.status === 401)
    return Response.json({ error: result.error }, { status: 401 });
  return Response.json({ ok: true, revalidated: result.revalidated });
}
