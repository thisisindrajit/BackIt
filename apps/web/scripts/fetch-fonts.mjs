// The Timeless fonts are licensed for web embedding but not for public repos,
// so they're gitignored and pulled from a private Vercel Blob store at build time.
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const FONTS = ["TimelessSerifVF.ttf", "TimelessSerifItalicVF.ttf", "TimelessSansVF.ttf"];
const dir = join(import.meta.dirname, "..", "src", "fonts");

const missing = FONTS.filter((f) => !existsSync(join(dir, f)));
if (missing.length === 0) process.exit(0);

const base = process.env.FONTS_BASE_URL?.replace(/\/$/, "");
const token = process.env.BLOB_READ_WRITE_TOKEN;
if (!base || !token) {
  console.error(
    `Missing fonts (${missing.join(", ")}) in src/fonts. Copy them in locally, or set FONTS_BASE_URL and BLOB_READ_WRITE_TOKEN.`,
  );
  process.exit(1);
}

await mkdir(dir, { recursive: true });
await Promise.all(
  missing.map(async (f) => {
    const res = await fetch(`${base}/${f}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Font download failed for ${f}: ${res.status}`);
    await writeFile(join(dir, f), Buffer.from(await res.arrayBuffer()));
    console.log(`Fetched ${f}`);
  }),
);
