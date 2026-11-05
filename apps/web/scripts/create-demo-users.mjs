// Creates (or resets the password of) the email/password demo accounts judges use.
// Usage: DEMO_BUILDER_PASSWORD=... DEMO_BACKER_PASSWORD=... node --env-file=.env.local scripts/create-demo-users.mjs
import { betterAuth } from "better-auth";
import { hashPassword } from "better-auth/crypto";
import pg from "pg";

const [host, port] = (process.env.DB_SERVER ?? "localhost").split(":");
const pool = new pg.Pool({
  host, port: Number(port ?? 5432), user: process.env.DB_USERNAME, password: process.env.DB_PASSWORD || undefined,
  database: process.env.DB_NAME, ssl: ["localhost", "127.0.0.1"].includes(host) ? false : { rejectUnauthorized: true },
  options: "-c search_path=auth",
});
// Sign-up is open only inside this script; the app itself disables it.
const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  database: pool,
  emailAndPassword: { enabled: true },
});

const users = [
  { email: "builder@demo.backit.club", name: "Ledgerly Team", password: process.env.DEMO_BUILDER_PASSWORD },
  { email: "backer@demo.backit.club", name: "Demo Backer", password: process.env.DEMO_BACKER_PASSWORD },
];

for (const u of users) {
  if (!u.password || u.password.length < 8) throw new Error(`Set a password (8+ chars) for ${u.email}`);
  const existing = await pool.query(`select id from "user" where email = $1`, [u.email]);
  if (existing.rowCount) {
    const id = existing.rows[0].id;
    await pool.query(`update account set password = $1 where "userId" = $2 and "providerId" = 'credential'`,
      [await hashPassword(u.password), id]);
    console.log(`${u.email} exists (${id}); password reset`);
  } else {
    const res = await auth.api.signUpEmail({ body: { email: u.email, password: u.password, name: u.name } });
    await pool.query(`update "user" set "emailVerified" = true where id = $1`, [res.user.id]);
    console.log(`${u.email} created (${res.user.id})`);
  }
}
await pool.end();
