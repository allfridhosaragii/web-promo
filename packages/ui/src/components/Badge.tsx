import type { ReactNode } from "react";
export function Badge({
  children,
  tone = "neutral",
}: { children: ReactNode; tone?: "neutral" | "sticker" | "label" | "valid" }) {
  const tones = {
    neutral: "border-[var(--bp-line)]",
    sticker: "bg-[var(--bp-sticker)] text-white border-transparent",
    label: "bg-[var(--bp-label)] text-black border-transparent",
    valid: "bg-[var(--bp-valid)] text-white border-transparent",
  } as const;
  return (
    <span
      className={`inline-flex items-center border px-2 py-0.5 text-xs font-semibold rounded ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
