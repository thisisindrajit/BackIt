# 🌐 BackIt web app

The Next.js app behind **[backit.club](https://backit.club)**: the landing page, Explore, campaign pages, PayPal checkout, and the builder and backer dashboards.

> 🏗️ How it fits with the API and PayPal: [docs/architecture.md](../../docs/architecture.md)

## 🧰 Stack

- ⚛️ **Next.js 16** (App Router) + React 19
- 🎨 **shadcn/ui** + **Tailwind CSS v4**, Timeless Serif and Timeless Sans fonts
- 🔐 **Better Auth** with Google sign-in and the JWT plugin (tokens for the API)
- 🔄 **TanStack Query** for data fetching, with API types generated from FastAPI's OpenAPI schema

## 🚀 Run it locally

Start Postgres, the API and the worker first (see the [root README](../../README.md#-local-setup)). Then:

```bash
cd apps/web
cp .env.example .env.local                           # set BETTER_AUTH_SECRET and Google OAuth keys
npm install
npx @better-auth/cli@latest migrate --config src/lib/auth.ts -y
npm run dev                                          # http://localhost:3000
```

🔤 **Fonts:** the Timeless fonts are licensed, so they're gitignored. Copy `TimelessSerifVF.ttf`, `TimelessSerifItalicVF.ttf` and `TimelessSansVF.ttf` into `src/fonts/`. On Vercel, `npm run build` runs `scripts/fetch-fonts.mjs` first and downloads them from a private Vercel Blob store.

## 🗺️ Pages

| Route | What you see |
|---|---|
| `/` | Landing page |
| `/explore` | 🔎 Public list of live campaigns (trending and new) |
| `/{slug}` | 📣 A campaign page. `?ref=CODE` shows the friend discount |
| `/{slug}/ledger` | 📒 Public ledger of sales, refunds and payouts |
| `/checkout/{orderId}` (+ `/return`, `/cancel`) | 💙 PayPal checkout and receipt |
| `/sign-in`, `/sign-up` | 🔑 Google sign-in |
| `/app` | 📊 Dashboard: weekly sales, rewards earned and sent |
| `/app/products`, `/app/products/new` | 🧱 Your products and the new-campaign flow (with the AI offer advisor) |
| `/app/products/{id}` | 🛠️ Setup, Campaign, Sales, Payouts and Webhooks tabs |
| `/app/backings` | 🏅 Things you backed: badge, access code, share link, rewards |
| `/app/explore` | 🔎 Explore, inside the app |
| `/app/settings` | ⚙️ Name and payout email |
| `/demo` | 🧩 Embeds the demo product to redeem an access code |

## 📁 Folders

```
src/app/          routes (see above) + /api/auth for Better Auth
src/components/
  ui/             shadcn/ui primitives
  backit/         shared app pieces: nav, header, badges, skeletons
  landing/  explore/  public/  builder/  backer/  dashboard/
src/lib/
  auth.ts         Better Auth server config (Google + JWT)
  auth-client.ts  Better Auth client
  api/            typed API client (schema.d.ts is generated)
  format.ts       money and date formatting
scripts/fetch-fonts.mjs
```

## ⚙️ Environment (`.env.local`)

| Variable | What it's for |
|---|---|
| `BETTER_AUTH_URL`, `BETTER_AUTH_SECRET` | Auth base URL and signing secret |
| `DB_SERVER`, `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME` | Postgres for the `auth` schema |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in |
| `NEXT_PUBLIC_API_URL` | The API, e.g. `http://localhost:8000/v1` |
| `NEXT_PUBLIC_DEMO_PRODUCT_URL` | The demo product, e.g. `http://localhost:8100` |
| `FONTS_BASE_URL`, `BLOB_READ_WRITE_TOKEN` | Build-time font download (Vercel only) |

## 🧹 Scripts

```bash
npm run dev          # dev server
npm run build        # fetch fonts, then production build
npm run lint         # ESLint
npx tsc --noEmit     # type check
npm run api:types    # regenerate src/lib/api/schema.d.ts from the API's OpenAPI
```
