import { betterAuth } from "better-auth";
import { jwt } from "better-auth/plugins";
import { nextCookies } from "better-auth/next-js";
import { Pool } from "pg";

const baseURL = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";

const [dbHost, dbPort] = (process.env.DB_SERVER ?? "localhost").split(":");
const isLocalDb = ["localhost", "127.0.0.1"].includes(dbHost);

export const auth = betterAuth({
  baseURL,
  database: new Pool({
    host: dbHost,
    port: Number(dbPort ?? 5432),
    user: process.env.DB_USERNAME,
    password: process.env.DB_PASSWORD || undefined,
    database: process.env.DB_NAME,
    ssl: isLocalDb ? false : { rejectUnauthorized: true },
    options: "-c search_path=auth",
  }),
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
      prompt: "select_account",
    },
  },
  trustedOrigins: [baseURL],
  plugins: [
    jwt({
      jwt: {
        issuer: baseURL,
        audience: baseURL,
        expirationTime: "15m",
        definePayload: ({ user }) => ({ email: user.email, name: user.name }),
      },
    }),
    nextCookies(),
  ],
});
