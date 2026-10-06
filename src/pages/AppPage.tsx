import { useNavigate } from "react-router";

import { useAuthUser } from "@/components/RequireAuth";
import { SiteHeader } from "@/components/SiteHeader";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { usePageMeta } from "@/lib/use-page-meta";

export default function AppPage() {
  usePageMeta({
    title: "Dashboard — Flight Price Notifier",
    description: "Your flight route tracking dashboard.",
    ogTitle: "Dashboard — Flight Price Notifier",
    ogDescription: "Your flight route tracking dashboard.",
  });
  const user = useAuthUser();
  const navigate = useNavigate();

  async function signOut() {
    await supabase.auth.signOut();
    navigate("/");
  }

  return (
    <div className="flex min-h-screen flex-col bg-hero">
      <SiteHeader right={<Button variant="secondary" onClick={signOut}>Sign out</Button>} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-20">
        <div className="animate-fade-up rounded-2xl border border-border bg-card p-10">
          <h1 className="text-3xl font-bold">Hi {user.email}</h1>
          <p className="mt-4 text-lg">你的航線追蹤儀表板即將上線 — 下一個里程碑會加上訂閱航線的功能。</p>
          <p className="mt-2 text-muted-foreground">
            Your dashboard is coming soon. Route-subscription will be added in the next milestone.
          </p>
        </div>
      </main>
    </div>
  );
}
