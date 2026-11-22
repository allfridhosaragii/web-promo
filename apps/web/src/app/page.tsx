import { PromoCard, SearchBar } from "@burupromo/ui";
import { fetchPromos } from "../lib/api";
// Halaman depan = langsung search bar + hasil, BUKAN hero (ARCHITECTURE.md §9).
const CATEGORIES = [
  "Makanan & Minuman",
  "Kebutuhan Harian",
  "Fashion",
  "Rumah & Perabot",
  "Elektronik & Gadget",
  "Kecantikan",
  "E-commerce",
  "Transportasi & Travel",
  "Keuangan",
  "Hiburan",
  "Pendidikan & Mahasiswa",
  "Pulsa, Data & Tagihan",
];
export default async function Home({
  searchParams,
}: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const { data, meta } = await fetchPromos(q ? { q } : {});
  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 pt-6">
      <SearchBar defaultValue={q ?? ""} />
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Kategori">
        {CATEGORIES.map((c) => (
          <a
            key={c}
            href={`/?q=${encodeURIComponent(c)}`}
            className="border rounded-full px-3 py-1 text-sm min-h-[44px] inline-flex items-center"
          >
            {c}
          </a>
        ))}
      </div>
      <section aria-label="Berakhir hari ini" className="mt-8">
        <h2 className="font-display text-xl font-bold">Berakhir hari ini</h2>
        {data.length === 0 ? (
          <p className="mt-2 border-2 border-dashed border-[var(--bp-line)] rounded-md p-4 text-[var(--bp-muted)]">
            Belum ada promo yang terindeks — Fase 0 skeleton. Setelah vertical
            slice BCA, promo BCA nyata akan tampil di sini ({meta.total} promo
            saat ini).
          </p>
        ) : (
          <div className="mt-4 grid gap-4">
            {data.map((p) => (
              <PromoCard key={p.id} promo={p} />
            ))}
          </div>
        )}
      </section>
      <section aria-label="Promo dekat kamu" className="mt-8">
        <h2 className="font-display text-xl font-bold">Promo dekat kamu</h2>
        <p className="mt-2 text-[var(--bp-muted)]">
          Aktif setelah Fase 3 (geolokasi + PostGIS). Geometri wilayah masih
          NULL di Fase 0 — lihat seed/wilayah/MANIFEST.md.
        </p>
      </section>
      <section aria-label="Paling banyak disimpan" className="mt-8">
        <h2 className="font-display text-xl font-bold">
          Paling banyak disimpan
        </h2>
        <p className="mt-2 text-[var(--bp-muted)]">Belum ada data.</p>
      </section>
    </div>
  );
}
