import type { PromoSummary } from "@burupromo/contracts";
import { Badge } from "./Badge";
import { Countdown } from "./Countdown";
import { VoucherCode } from "./VoucherCode";
/** Kartu promo seperti label harga — ARCHITECTURE.md §9. Angka diskon BESAR sebagai fokus. */
export function PromoCard({ promo }: { promo: PromoSummary }) {
  const big =
    promo.promo_type === "gratis_ongkir"
      ? "GRATIS ONGKIR"
      : promo.value_percent != null
        ? `-${promo.value_percent}%`
        : promo.value_amount != null
          ? `Rp${promo.value_amount.toLocaleString("id-ID")}`
          : "PROMO";
  return (
    <article className="border-2 border-[var(--bp-ink)] bg-white rounded-md p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-display text-4xl font-bold leading-none text-[var(--bp-sticker)]">
          {big}
        </p>
        <Badge tone={promo.status === "segera_berakhir" ? "sticker" : "valid"}>
          {promo.status === "segera_berakhir" ? "Segera berakhir" : "Aktif"}
        </Badge>
      </div>
      <h3 className="mt-3 font-semibold text-lg leading-snug">{promo.title}</h3>
      <p className="mt-1 text-sm text-[var(--bp-muted)]">{promo.summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge>{promo.brand.name}</Badge>
        <Badge>
          {promo.region_scope === "nasional"
            ? "Nasional"
            : `Berlaku di ${promo.region_codes.join(", ") || "Surabaya"}`}
        </Badge>
        <Badge>Dari sumber resmi</Badge>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        {promo.voucher_code ? (
          <VoucherCode code={promo.voucher_code} />
        ) : (
          <span className="text-sm">Tanpa kode voucher</span>
        )}
        <Countdown endsAt={promo.ends_at} />
      </div>
      <a
        href={promo.source_url}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-block text-sm font-semibold underline"
      >
        Lihat di sumber
      </a>
    </article>
  );
}
