import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { APP_NAME } from "../lib/constants";

// Umami self-host (Rp0, ARCH §3.5.3): script hanya di-load bila
// NEXT_PUBLIC_UMAMI_WEBSITE_ID diisi. Tanpa itu, tidak ada tracking.
const UMAMI_WEBSITE_ID = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID;
const UMAMI_SCRIPT_URL =
  process.env.NEXT_PUBLIC_UMAMI_SCRIPT_URL ?? "/umami/script.js";
export const metadata: Metadata = {
  title: `${APP_NAME} — Cari promo yang masih berlaku`,
  description:
    "Search engine khusus promo Indonesia. Jawa Timur dulu, fokus Surabaya.",
  manifest: "/manifest.webmanifest",
};
export default function RootLayout({
  children,
}: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        {UMAMI_WEBSITE_ID ? (
          <Script
            src={UMAMI_SCRIPT_URL}
            data-website-id={UMAMI_WEBSITE_ID}
            strategy="afterInteractive"
          />
        ) : null}
        <header className="border-b-2 border-[var(--bp-ink)] px-4 py-3">
          <p className="font-display text-2xl font-bold">{APP_NAME}</p>
          <p className="text-sm text-[var(--bp-muted)]">
            Promo yang masih berlaku — Jawa Timur, fokus Surabaya
          </p>
        </header>
        <main>{children}</main>
        <nav
          aria-label="Navigasi utama"
          className="fixed bottom-0 inset-x-0 border-t-2 border-[var(--bp-ink)] bg-[var(--bp-paper)] flex justify-around py-2 text-sm font-semibold"
        >
          <a href="/">Cari</a>
          <a href="/?view=dekat">Dekat</a>
          <a href="/?view=disimpan">Disimpan</a>
          <a href="/?view=notifikasi">Notifikasi</a>
          <a href="/?view=akun">Akun</a>
        </nav>
      </body>
    </html>
  );
}
