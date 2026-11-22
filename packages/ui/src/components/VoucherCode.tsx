"use client";
import { useState } from "react";
/** Kode voucher dalam kotak bergaris putus-putus (gaya kupon sobek) + tombol salin. */
export function VoucherCode({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      /* clipboard tidak tersedia */
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <span className="inline-flex items-center gap-2">
      <code className="border-2 border-dashed border-[var(--bp-ink)] px-2 py-1 font-mono text-sm font-bold tracking-wide">
        {code}
      </code>
      <button
        type="button"
        onClick={copy}
        aria-live="polite"
        className="min-h-[44px] px-3 border rounded font-semibold text-sm"
      >
        {copied ? "Tersalin" : "Salin"}
      </button>
    </span>
  );
}
