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
    <article className="border-2 border-[var(--bp-ink)] bg-[var(--bp-surface)] text-[var(--bp-ink)] rounded-md p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-display text-4xl font-bold leading-none text-[var(--bp-sticker)]">
          {big}
        </p>
        <Badge
          tone={
            promo.lifecycle === "segera_berakhir"
              ? "sticker"
              : promo.lifecycle === "kedaluwarsa"
                ? "sticker"
                : "valid"
          }
        >
          {promo.lifecycle === "segera_berakhir"
            ? "Segera berakhir"
            : promo.lifecycle === "kedaluwarsa"
              ? "Promo sudah berakhir"
              : promo.lifecycle === "dijadwalkan"
                ? "Dijadwalkan"
                : "Aktif"}
        </Badge>
      </div>
      <h3 className="mt-3 font-semibold text-lg leading-snug">
        <a href={`/promo/${promo.id}`} className="hover:underline">
          {promo.title}
        </a>
      </h3>
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
      {promo.lifecycle === "kedaluwarsa" ? (
        <p className="mt-3 border-2 border-dashed border-[var(--bp-line)] rounded-md p-3 text-sm">
          Promo sudah berakhir — detail ini disimpan sebagai arsip. Lihat promo
          serupa yang masih berlaku di halaman depan.
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm font-semibold">
        <a href={`/promo/${promo.id}`} className="underline">
          Detail promo
        </a>
        <a
          href={promo.source_url}
          target="_blank"
          rel="noreferrer"
          className="underline text-[var(--bp-muted)]"
        >
          Lihat di sumber
        </a>
      </div>
    </article>
  );
}
