// Jalankan migrasi SQL di ./migrations secara berurutan. Butuh DATABASE_URL.
import { readFileSync, readdirSync } from "node:fs";
import { Client } from "pg";
const url = process.env.DATABASE_URL;
if (!url) {
  console.error("DATABASE_URL belum diisi (lihat .env.example)");
  process.exit(1);
}
const files = readdirSync(new URL("../migrations", import.meta.url).pathname)
  .filter((f) => f.endsWith(".sql"))
  .sort();
const client = new Client({ connectionString: url });
await client.connect();
for (const f of files) {
  console.log(`Migrasi: ${f}`);
  await client.query(
    readFileSync(new URL(`../migrations/${f}`, import.meta.url), "utf8"),
  );
}
await client.end();
console.log("Migrasi selesai.");
