// Seed wilayah Jawa Timur dari CSV snapshot (Kepmendagri 300.2.2-2138-2025).
// GAGAL kalau jumlah kab/kota bukan 38. Jangan hardcode daftar di kode.
import { readFileSync } from "node:fs";
import { Client } from "pg";

const CSV = new URL(
  "./wilayah/kepmendagri-300.2.2-2138-2025.csv",
  import.meta.url,
);
const EXPECTED_KAB_KOTA = 38;

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.trim().split("\n");
  const first = lines[0];
  if (!first) return [];
  // Header CSV memakai `code_dagri`; normalisasi ke `code` (kolom regions.code).
  const header = first.split(",").map((h) => (h === "code_dagri" ? "code" : h));
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ""]));
  });
}

const rows = parseCsv(readFileSync(CSV, "utf8"));
const kabKota = rows.filter((r) => r.level === "kab_kota");
const provinsi = rows.filter((r) => r.level === "provinsi");
const prov = provinsi[0];
if (provinsi.length !== 1 || !prov || prov.code !== "35") {
  console.error(
    `Seed gagal: provinsi Jawa Timur (35) tidak ditemukan, dapat ${provinsi.length}`,
  );
  process.exit(1);
}
if (kabKota.length !== EXPECTED_KAB_KOTA) {
  console.error(
    `Seed gagal: kab/kota Jawa Timur harus ${EXPECTED_KAB_KOTA}, dapat ${kabKota.length}. Periksa MANIFEST.md.`,
  );
  process.exit(1);
}
const codes = new Set(kabKota.map((r) => r.code));
if (codes.size !== EXPECTED_KAB_KOTA) {
  console.error("Seed gagal: ada kode kab/kota duplikat.");
  process.exit(1);
}

const url = process.env.DATABASE_URL;
if (!url) {
  console.error(
    "DATABASE_URL belum diisi. Validasi file lolos (38 kab/kota), tapi insert dibatalkan.",
  );
  process.exit(1);
}
const client = new Client({ connectionString: url });
await client.connect();
for (const r of rows) {
  await client.query(
    `INSERT INTO regions (code, name, level, parent_code, cluster) VALUES ($1,$2,$3,$4,$5)
     ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, level=EXCLUDED.level, parent_code=EXCLUDED.parent_code, cluster=EXCLUDED.cluster`,
    [r.code, r.name, r.level, r.parent_code || null, r.cluster || null],
  );
}
await client.end();
console.log(
  `Seed wilayah selesai: 1 provinsi + ${kabKota.length} kab/kota Jawa Timur.`,
);
