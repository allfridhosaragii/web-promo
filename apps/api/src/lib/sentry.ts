// Sentry Developer (free tier, Rp0) — ARCH §3.5.3, revisi 2.
// Batas: 5.000 error/bulan, 1 user, retensi 30 hari, 50 replay/bulan.
// Event di-drop bila habis — TIDAK ditagih (Developer plan tanpa pay-as-you-go).
// Sampling rendah (traces 0.1), replay MATI secara default.
// Tanpa SENTRY_DSN, initSentry() no-op — API tetap jalan tanpa Sentry.
// SDK @sentry/node di-import dinamis supaya `pnpm typecheck` tetap jalan
// bila paket belum terpasang; pasang dengan `pnpm add @sentry/node` sebelum deploy.
export function initSentry(): void {
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return;
  void import("@sentry/node")
    .then((Sentry) => {
      Sentry.init({
        dsn,
        tracesSampleRate: 0.1,
        // Tidak ada opsi replay di @sentry/node — replay hanya ada di SDK browser.
        // Di server tidak ada replay yang tercatat, jadi kuota 50 replay/bulan aman.
        environment: process.env.NODE_ENV ?? "development",
      });
    })
    .catch(() => {
      console.warn(
        "[sentry] @sentry/node belum terpasang — jalankan `pnpm add @sentry/node`. Error tracking nonaktif.",
      );
    });
}
