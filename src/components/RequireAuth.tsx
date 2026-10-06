import type { User } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { Navigate, Outlet, useOutletContext } from "react-router";

import { supabase } from "@/integrations/supabase/client";

type AuthContext = { user: User };

// Replaces the `_authenticated` layout route: verify the Supabase user on the
// client, redirect to /signin if missing, and expose `user` to child routes.
export function RequireAuth() {
  const [state, setState] = useState<{ status: "loading" } | { status: "ready"; user: User | null }>({
    status: "loading",
  });

  useEffect(() => {
    let cancelled = false;
    supabase.auth.getUser().then(({ data, error }) => {
      if (!cancelled) setState({ status: "ready", user: error ? null : data.user });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") return <div className="min-h-screen bg-hero" />;
  if (!state.user) return <Navigate to="/signin" replace />;
  return <Outlet context={{ user: state.user } satisfies AuthContext} />;
}

export function useAuthUser() {
  return useOutletContext<AuthContext>().user;
}
