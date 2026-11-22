import { PromoCard } from "@burupromo/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchPromoById, fetchPromos } from "../../../lib/api";

// Halaman detail promo (ARCH §16.1, perbaikan A6).
// - lifecycle=kedaluwarsa -> tetap 200, tampil "Promo sudah berakhir" +
//   promo serupa, meta robots noindex (jangan diindeks Google sebagai aktif).
// - 404 hanya untuk id tidak ada / moderation=ditolak (API mengembalikan null).
export async function generateMetadata({
  params,
}: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const promo = await fetchPromoById(id);
  if (promo === null) return { title: "Promo tidak ditemukan — BuruPromo" };
  if (promo.lifecycle === "kedaluwarsa")
    return {
      title: `${promo.title} (sudah berakhir) — BuruPromo`,
      robots: { index: false, follow: true },
    };
  return { title: `${promo.title} — BuruPromo`, description: promo.summary };
}

export default async function PromoDetailPage({
  params,
}: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const promo = await fetchPromoById(id);
  if (promo === null) notFound();
  const expired = promo.lifecycle === "kedaluwarsa";
  // Promo serupa: kategori/brand yang sama, masih aktif (list utama).
  const { data: similar } = await fetchPromos(
    promo.category_slugs[0]
      ? { category: promo.category_slugs[0] }
      : { brand: promo.brand.slug },
  );
  const others = similar.filter((p) => p.id !== promo.id).slice(0, 5);
  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 pt-6">
      {expired ? (
        <p className="border-2 border-[var(--bp-sticker)] rounded-md p-4 font-semibold">
          Promo sudah berakhir. Detail ini disimpan sebagai arsip — jangan
          dipakai untuk klaim. Di bawah ada promo serupa yang masih berlaku.
        </p>
      ) : null}
      <div className="mt-4">
        <PromoCard promo={promo} />
      </div>
      <section aria-label="Promo serupa" className="mt-8">
        <h2 className="font-display text-xl font-bold">Promo serupa</h2>
        {others.length === 0 ? (
          <p className="mt-2 text-[var(--bp-muted)]">
            Belum ada promo serupa yang terindeks.
          </p>
        ) : (
          <div className="mt-4 grid gap-4">
            {others.map((p) => (
              <PromoCard key={p.id} promo={p} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
