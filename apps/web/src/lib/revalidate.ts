// Logika revalidate — murni, bisa di-test tanpa Next.js (ARCH §17.4, perbaikan F).
// Hono (API) tidak bisa memanggil revalidatePath langsung, jadi worker/API
// memanggil route handler POST /api/revalidate di web ini (lihat
// src/app/api/revalidate/route.ts) dengan secret di header x-revalidate-secret.
// Secret kosong di env = revalidate MATI (fail closed, 401).
export type Revalidator = {
  revalidatePath: (path: string) => void;
  revalidateTag: (tag: string) => void;
};

export type RevalidateResult =
  | { status: 200; revalidated: { paths: string[]; tags: string[] } }
  | { status: 401; error: string };

export function handleRevalidate(input: {
  configuredSecret: string | undefined;
  providedSecret: string | null;
  // `| undefined` eksplisit: tsconfig memakai exactOptionalPropertyTypes,
  // pemanggil boleh mengirim properti bernilai undefined.
  paths?: string[] | undefined;
  tags?: string[] | undefined;
  revalidator: Revalidator;
}): RevalidateResult {
  if (!input.configuredSecret)
    return { status: 401, error: "REVALIDATE_SECRET belum dikonfigurasi" };
  if (input.providedSecret !== input.configuredSecret)
    return { status: 401, error: "Secret salah" };
  // Hanya path absolut yang diizinkan — jangan biarkan pemanggil memasukkan
  // path aneh. Default: halaman depan + tag promos.
  const paths = (input.paths ?? ["/"]).filter((p) => p.startsWith("/"));
  const tags = input.tags ?? ["promos"];
  for (const p of paths) input.revalidator.revalidatePath(p);
  for (const t of tags) input.revalidator.revalidateTag(t);
  return { status: 200, revalidated: { paths, tags } };
}
