# Pixel Perfect Replica

Implement exactly the screenshot and nothing else

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/bb890364-c4d5-45a7-b6cd-9b7538116ecf).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
bun install   # or: npm i
bun run dev   # or: npm run dev
```

## Architecture

Plain **Vite + React** single-page app — no SSR, no server runtime.

- Routing: React Router (`src/App.tsx`) — `/`, `/signin`, `/signup`, `/app` (requires a Supabase session; redirects to `/signin` otherwise), and a 404 fallback.
- Auth: Supabase JS client in the browser (`src/integrations/supabase/client.ts`).
- Build: `vite build` → static files in `dist/`.

## Deploy to Vercel

1. Import the repo in Vercel (framework preset: **Vite**; `vercel.json` already sets the build command and `dist` output).
2. Add environment variables `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` (see `.env`). They're inlined at build time.
3. `vercel.json` rewrites every path to `/index.html`, so deep links like `/app` resolve client-side.
4. In Supabase → Authentication → URL Configuration, add your Vercel domain (e.g. `https://<project>.vercel.app/app`) to the redirect URLs so sign-up confirmation emails land back on the app.
