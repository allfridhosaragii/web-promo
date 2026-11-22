// BuruPromo design tokens — ARCHITECTURE.md §9 "Label Harga & Struk Belanja".
// Larangan: gradien ungu-biru, glassmorphism, blob, glow neon, rounded-2xl seragam.
const tokens = require("../ui/src/tokens.cjs");
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        paper: tokens.colors.paper,
        ink: tokens.colors.ink,
        line: tokens.colors.line,
        sticker: tokens.colors.sticker,
        label: tokens.colors.label,
        valid: tokens.colors.valid,
        muted: tokens.colors.muted,
        night: tokens.colors.night,
        nightSurface: tokens.colors.nightSurface,
        nightText: tokens.colors.nightText,
      },
      fontFamily: {
        display: ["Bricolage Grotesque", "system-ui", "sans-serif"],
        sans: ["Schibsted Grotesk", "Inter Tight", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { sm: "4px", DEFAULT: "6px", md: "8px" },
      spacing: { 11: "2.75rem" },
    },
  },
  plugins: [],
};
