import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/SiteHeader";

export const Route = createFileRoute("/_authenticated/app")({
  head: () => ({
    meta: [
      { title: "Dashboard — Flight Price Notifier" },
      { name: "description", content: "Your flight route tracking dashboard." },
      { property: "og:title", content: "Dashboard — Flight Price Notifier" },
      { property: "og:description", content: "Your flight route tracking dashboard." },
    ],
  }),
  component: AppPage,
});

function AppPage() {
  const { user } = Route.useRouteContext();
  const navigate = useNavigate();

  async function signOut() {
    await supabase.auth.signOut();
    navigate({ to: "/" });
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
