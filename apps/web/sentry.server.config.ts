// Sentry Developer (free tier, Rp0) — server. ARCH §3.5.3, revisi 2.
// Tanpa SENTRY_DSN, file ini no-op.
import * as Sentry from "@sentry/nextjs";

if (process.env.SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    environment: process.env.NODE_ENV ?? "development",
  });
}
