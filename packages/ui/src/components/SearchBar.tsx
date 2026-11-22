"use client";
import { useState } from "react";
export function SearchBar({
  defaultValue = "",
  onSearch,
}: { defaultValue?: string; onSearch?: (q: string) => void }) {
  const [q, setQ] = useState(defaultValue);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSearch?.(q);
      }}
    >
      <label htmlFor="bp-search" className="sr-only">
        Cari promo
      </label>
      <input
        id="bp-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Cari promo: kopi, gratis ongkir, promo BCA…"
        className="w-full min-h-[44px] border-2 border-[var(--bp-ink)] bg-white px-4 py-3 text-base rounded-md"
      />
    </form>
  );
}
