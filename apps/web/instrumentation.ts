// Next.js 15: daftarkan Sentry server saat runtime Node.js.
// Tanpa SENTRY_DSN, sentry.server.config.ts no-op.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
}
