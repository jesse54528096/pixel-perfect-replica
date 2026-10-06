import { createClient } from "@supabase/supabase-js";
import type { Database } from "./types";

// Browser-only Supabase client. Values are inlined by Vite at build time from
// .env locally and from the Vercel project's Environment Variables in production.
const SUPABASE_URL = import.meta.env["VITE_SUPABASE_URL"];
const SUPABASE_PUBLISHABLE_KEY = import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"];

if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
  const missing = [
    ...(!SUPABASE_URL ? ["VITE_SUPABASE_URL"] : []),
    ...(!SUPABASE_PUBLISHABLE_KEY ? ["VITE_SUPABASE_PUBLISHABLE_KEY"] : []),
  ];
  const message = `Missing Supabase environment variable(s): ${missing.join(", ")}. Set them in .env locally and in the Vercel project's Environment Variables.`;
  console.error(`[Supabase] ${message}`);
  throw new Error(message);
}

function isNewSupabaseApiKey(value: string): boolean {
  return value.startsWith("sb_publishable_") || value.startsWith("sb_secret_");
}

// New sb_publishable_* keys are opaque strings, not bearer JWTs: send them only
// as the `apikey` header, never as `Authorization: Bearer <key>`.
function createSupabaseFetch(supabaseKey: string): typeof fetch {
  return (input, init) => {
    const headers = new Headers(
      typeof Request !== "undefined" && input instanceof Request ? input.headers : undefined,
    );
    if (init?.headers) {
      new Headers(init.headers).forEach((value, key) => headers.set(key, value));
    }
    if (isNewSupabaseApiKey(supabaseKey) && headers.get("Authorization") === `Bearer ${supabaseKey}`) {
      headers.delete("Authorization");
    }
    headers.set("apikey", supabaseKey);
    return fetch(input, { ...init, headers });
  };
}

// The single Supabase client for the app. Import it like this:
// import { supabase } from "@/integrations/supabase/client";
export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  global: { fetch: createSupabaseFetch(SUPABASE_PUBLISHABLE_KEY) },
  auth: {
    storage: typeof window !== "undefined" ? window.localStorage : undefined,
    persistSession: true,
    autoRefreshToken: true,
  },
});
