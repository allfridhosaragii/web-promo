import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

export * from "./schema";

let _pool: Pool | null = null;

export function getPool(connectionString?: string): Pool {
  if (_pool) return _pool;
  const url = connectionString ?? process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL belum diisi (lihat .env.example)");
  _pool = new Pool({ connectionString: url });
  return _pool;
}

export function getDb(connectionString?: string) {
  return drizzle(getPool(connectionString), { schema });
}
