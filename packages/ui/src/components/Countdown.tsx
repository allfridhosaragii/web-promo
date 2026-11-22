/** Hitung mundur sederhana dari ends_at (ISO UTC) ke WIB. Tanpa jam hidup di Fase 0.
 * endsAt null = "Tanpa batas waktu" (ARCH §5.3, A5). */
export function Countdown({ endsAt }: { endsAt: string | null }) {
  if (endsAt == null)
    return (
      <span className="font-semibold text-[var(--bp-valid)]">
        Tanpa batas waktu
      </span>
    );
  const end = new Date(endsAt).getTime();
  const diffMs = end - Date.now();
  if (diffMs <= 0)
    return (
      <span className="font-semibold text-[var(--bp-sticker)]">Berakhir</span>
    );
  const hours = Math.floor(diffMs / 3_600_000);
  const days = Math.floor(hours / 24);
  const label =
    days >= 1 ? `Berakhir ${days} hari lagi` : `Berakhir ${hours} jam lagi`;
  const urgent = hours < 24;
  return (
    <span
      className={`font-semibold ${urgent ? "text-[var(--bp-sticker)]" : ""}`}
    >
      {label}
    </span>
  );
}
