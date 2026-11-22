// Fase 0: belum ada koneksi DB sungguhan di handler. DATABASE_URL dibaca di sini
// saat migrasi/seed dijalankan; handler /v1 mengembalikan data kosong yang jujur.
export function requireDatabaseUrl(): string {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL belum diisi (lihat .env.example)");
  return url;
}
