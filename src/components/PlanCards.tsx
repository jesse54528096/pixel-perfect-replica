import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  listSubscriptions,
  saveSubscription,
  type PlanName,
  type Subscription,
} from "@/lib/flight-api";

const PLANS: { name: PlanName; title: string; route: string; hint: number }[] = [
  { name: "tokyo", title: "台北 ✈ 東京", route: "TPE-TYO", hint: 9325 },
  { name: "seoul", title: "台北 ✈ 首爾", route: "TPE-SEL", hint: 5989 },
];

const formatTwd = (n: number) => `NT$${n.toLocaleString("en-US")}`;

function PlanCard({
  plan,
  email,
  subscription,
  onSaved,
}: {
  plan: (typeof PLANS)[number];
  email: string;
  subscription?: Subscription | undefined;
  onSaved: (sub: Subscription) => void;
}) {
  const [editing, setEditing] = useState(!subscription);
  const [price, setPrice] = useState(String(subscription?.target_price ?? ""));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEditing(!subscription);
    if (subscription) setPrice(String(subscription.target_price));
  }, [subscription]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const target = Number(price);
    if (!Number.isFinite(target) || target <= 0) {
      setError("請輸入大於 0 的目標價（新台幣）");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveSubscription(email, plan.name, target);
      onSaved({
        email,
        route: plan.route,
        plan_name: plan.name,
        target_price: target,
        currency: "TWD",
      });
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "訂閱失敗，請稍後再試");
    } finally {
      setSaving(false);
    }
  }

  const inputId = `target-${plan.name}`;
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-bold">{plan.title}</h2>
        {subscription && <Badge>已訂閱 / Subscribed</Badge>}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        最近查到的最低價約 {formatTwd(plan.hint)}
      </p>

      {subscription && !editing ? (
        <div className="mt-5 flex items-center justify-between gap-3">
          <p>
            目標價 <span className="font-semibold">{formatTwd(subscription.target_price)}</span>
          </p>
          <Button variant="secondary" onClick={() => setEditing(true)}>
            更新目標價 / Update
          </Button>
        </div>
      ) : (
        <form className="mt-5 space-y-3" onSubmit={submit}>
          <Label htmlFor={inputId}>目標價（新台幣）</Label>
          <div className="flex gap-3">
            <Input
              id={inputId}
              type="number"
              inputMode="numeric"
              min={1}
              placeholder={String(plan.hint)}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
            <Button type="submit" disabled={saving}>
              {saving ? "儲存中…" : subscription ? "儲存" : "開始追蹤"}
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      )}
    </div>
  );
}

export function PlanCards({ email }: { email: string }) {
  const [subs, setSubs] = useState<Record<string, Subscription>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSubscriptions(email)
      .then((items) => {
        if (!cancelled) setSubs(Object.fromEntries(items.map((s) => [s.route, s])));
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "讀取訂閱失敗");
      });
    return () => {
      cancelled = true;
    };
  }, [email]);

  return (
    <section className="space-y-4">
      {loadError && <p className="text-sm text-destructive">{loadError}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.name}
            plan={plan}
            email={email}
            subscription={subs[plan.route]}
            onSaved={(sub) => setSubs((prev) => ({ ...prev, [sub.route]: sub }))}
          />
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        每 30 分鐘查一次下個月的最低票價，達到目標價就寄 email 到 {email}。
      </p>
    </section>
  );
}
