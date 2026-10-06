# Flight Price Notifier

Set a route and a target price — get emailed when the fare drops.

## Development

You need Node.js and npm (or Bun) — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
bun install   # or: npm i
bun run dev   # or: npm run dev
```

## Architecture

Plain **Vite + React** single-page app — no SSR, no server runtime.

- Routing: React Router (`src/App.tsx`) — `/`, `/signin`, `/signup`, `/app` (requires a Supabase session; redirects to `/signin` otherwise), and a 404 fallback.
- Auth: Supabase JS client in the browser (`src/integrations/supabase/client.ts`), pointed at Supabase project `hznyrlxjaitimpixcqoy` via `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` in `.env`. The publishable key (`sb_publishable_*`) is Supabase's replacement for the old anon key: browser-safe and RLS-gated.
- Build: `vite build` → static files in `dist/`.

## Deploy to Vercel

1. Import the repo in Vercel (framework preset: **Vite**; `vercel.json` already sets the build command and `dist` output).
2. Add environment variables `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` with the same values as `.env`. They're inlined at build time, so redeploy after changing them.
3. `vercel.json` rewrites every path to `/index.html`, so deep links like `/app` resolve client-side.
4. In Supabase → Authentication → URL Configuration, add your Vercel domain (e.g. `https://<project>.vercel.app/app`) to the redirect URLs so sign-up confirmation emails land back on the app.
