// Design tokens BuruPromo — ARCHITECTURE.md §9. Satu sumber kebenaran warna/tipografi.
export const APP_NAME = "BuruPromo" as const;
export const colors = {
  paper: "#F6F3EC",
  ink: "#151515",
  line: "#D9D3C7",
  sticker: "#E4572E", // merah stiker — diskon / urgensi
  label: "#FFD23F", // kuning label — highlight
  valid: "#1F7A4C", // hijau valid
  muted: "#6B665E",
  night: "#121110",
  nightSurface: "#1C1B19",
  nightText: "#EDE8DE",
} as const;
export const fonts = {
  display: "Bricolage Grotesque",
  sans: "Schibsted Grotesk",
  mono: "JetBrains Mono",
} as const;
export const radius = { sm: 4, base: 6, md: 8 } as const;
export const minTouchTargetPx = 44;
