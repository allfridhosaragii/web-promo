// Sentry Developer (free tier, Rp0) — client. ARCH §3.5.3, revisi 2.
// Batas: 5.000 error/bulan, 1 user, retensi 30 hari. Event di-drop bila habis.
// Sampling rendah, replay MATI. Tanpa NEXT_PUBLIC_SENTRY_DSN, file ini no-op.
import * as Sentry from "@sentry/nextjs";

if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    environment: process.env.NODE_ENV ?? "development",
  });
}
