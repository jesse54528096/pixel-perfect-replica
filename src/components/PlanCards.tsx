import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import {
  cancelSubscription,
  listLatestPrices,
  listSubscriptions,
  type LatestPrice,
  saveSubscription,
  type PlanName,
  type Subscription,
} from "@/lib/flight-api";

const PLANS: { name: PlanName; title: string; route: string }[] = [
  { name: "tokyo", title: "台北 ✈ 東京", route: "TPE-TYO" },
  { name: "seoul", title: "台北 ✈ 首爾", route: "TPE-SEL" },
];

// Display only; the amount actually charged comes from the flight/ecpay secret on the server.
const MONTHLY_PRICE_TWD = 300;

const formatTwd = (n: number) => `NT$${n.toLocaleString("en-US")}`;

function formatCheckedAt(iso: string) {
  return new Date(iso).toLocaleString("zh-TW", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type CardState = "none" | "pending" | "active" | "grace" | "expired";

function cardState(sub: Subscription | undefined): CardState {
  if (!sub) return "none";
  switch (sub.subscription_status) {
    case "active":
      return "active";
    case "cancelled":
      return (sub.current_period_end ?? "") >= new Date().toISOString().slice(0, 19) + "Z"
        ? "grace"
        : "expired";
    case "expired":
      return "expired";
    default:
      return "pending"; // pending_payment, or a row saved before payments existed
  }
}

const BADGES: Record<
  Exclude<CardState, "none">,
  { label: string; variant: BadgeProps["variant"] }
> = {
  active: { label: "已訂閱（有效）", variant: "default" },
  pending: { label: "未完成付款", variant: "destructive" },
  grace: { label: "已取消", variant: "secondary" },
  expired: { label: "已結束", variant: "outline" },
};

function PlanCard({
  plan,
  email,
  subscription,
  latest,
  onSaved,
}: {
  plan: (typeof PLANS)[number];
  email: string;
  subscription?: Subscription | undefined;
  latest?: LatestPrice | undefined;
  onSaved: (sub: Subscription) => void;
}) {
  const state = cardState(subscription);
  const paying = state === "active" || state === "grace";
  const [editing, setEditing] = useState(state === "none" || state === "expired");
  const [price, setPrice] = useState(String(subscription?.target_price ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEditing(state === "none" || state === "expired");
    if (subscription) setPrice(String(subscription.target_price));
  }, [subscription, state]);

  async function save(target: number) {
    setBusy(true);
    setError(null);
    try {
      const result = await saveSubscription(email, plan.name, target);
      if (result.redirected) return; // the browser is on its way to ECPay
      onSaved({ ...subscription, ...result.subscription });
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "訂閱失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const target = Number(price);
    if (!Number.isFinite(target) || target <= 0) {
      setError("請輸入大於 0 的目標價（新台幣）");
      return;
    }
    void save(target);
  }

  async function cancel() {
    if (!subscription) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) throw new Error("登入已過期，請重新登入");
      const res = await cancelSubscription(email, plan.route, token);
      const next: Subscription = { ...subscription, subscription_status: "cancelled" };
      const end = res.current_period_end ?? subscription.current_period_end;
      const endDate = res.current_period_end_date ?? subscription.current_period_end_date;
      if (end) next.current_period_end = end;
      if (endDate) next.current_period_end_date = endDate;
      onSaved(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  const inputId = `target-${plan.name}`;
  const endDate = subscription?.current_period_end_date;
  const submitLabel = paying ? "儲存" : `訂閱並付款 ${formatTwd(MONTHLY_PRICE_TWD)}/月`;

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-bold">{plan.title}</h2>
        {state !== "none" && <Badge variant={BADGES[state].variant}>{BADGES[state].label}</Badge>}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {latest
          ? `${latest.month.slice(5)} 月最低價 ${formatTwd(latest.price)}（${formatCheckedAt(latest.checked_at)} 更新）`
          : "最低價查詢中…"}
      </p>

      {state === "active" && endDate && (
        <p className="mt-3 text-sm">
          月費 {formatTwd(MONTHLY_PRICE_TWD)}，下次扣款 {endDate}
        </p>
      )}
      {state === "grace" && endDate && (
        <p className="mt-3 text-sm">已取消，不會再扣款；{endDate} 前仍會通知你。</p>
      )}
      {state === "pending" && <p className="mt-3 text-sm">付款完成後才會開始通知。</p>}
      {state === "expired" && <p className="mt-3 text-sm">訂閱已結束，重新訂閱即可恢復通知。</p>}

      {subscription && !editing ? (
        <div className="mt-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p>
              目標價 <span className="font-semibold">{formatTwd(subscription.target_price)}</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {state === "pending" && (
                <Button disabled={busy} onClick={() => void save(subscription.target_price)}>
                  {busy ? "前往付款…" : `完成付款 ${formatTwd(MONTHLY_PRICE_TWD)}/月`}
                </Button>
              )}
              <Button variant="secondary" disabled={busy} onClick={() => setEditing(true)}>
                更新目標價
              </Button>
              {state === "active" && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" disabled={busy}>
                      取消訂閱
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>確定要取消 {plan.title} 的訂閱？</AlertDialogTitle>
                      <AlertDialogDescription>
                        取消後不會再扣款。
                        {endDate ? `已付費的期間內（到 ${endDate}）` : "已付費的期間內"}
                        仍會繼續通知你。
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>先不要</AlertDialogCancel>
                      <AlertDialogAction onClick={() => void cancel()}>確定取消</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
      ) : (
        <form className="mt-5 space-y-3" onSubmit={submit}>
          <Label htmlFor={inputId}>目標價（新台幣）</Label>
          <div className="flex flex-wrap gap-3">
            <Input
              id={inputId}
              className="min-w-0 flex-1"
              type="number"
              inputMode="numeric"
              min={1}
              placeholder={latest ? String(latest.price) : undefined}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
            <Button type="submit" disabled={busy}>
              {busy ? "處理中…" : submitLabel}
            </Button>
          </div>
          {!paying && (
            <p className="text-xs text-muted-foreground">
              透過綠界 ECPay 信用卡定期定額付款，每月自動扣款，可隨時取消。
            </p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      )}
    </div>
  );
}

export function PlanCards({ email }: { email: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const purchase = searchParams.get("purchase");
  const [subs, setSubs] = useState<Record<string, Subscription>>({});
  const [prices, setPrices] = useState<Record<string, LatestPrice>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(
    purchase === "success"
      ? "付款完成，正在開通訂閱…"
      : purchase === "failed"
        ? "付款沒有完成，可以再試一次。"
        : null,
  );

  useEffect(() => {
    let cancelled = false;
    listLatestPrices()
      .then((items) => {
        if (!cancelled) setPrices(Object.fromEntries(items.map((p) => [p.route, p])));
      })
      .catch(() => {
        // Prices are a hint only; the cards still work without them.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // After returning from ECPay, the payment callback can land a moment later: poll briefly.
    let polls = purchase === "success" ? 10 : 0;

    const load = () =>
      listSubscriptions(email)
        .then((items) => {
          if (cancelled) return;
          setSubs(Object.fromEntries(items.map((s) => [s.route, s])));
          if (polls > 0) {
            const pending = items.some((s) => cardState(s) === "pending");
            if (!pending) {
              setNotice("訂閱已開通，降價時會寄信通知你。");
              polls = 0;
            } else if (--polls > 0) {
              timer = setTimeout(load, 3000);
            } else {
              setNotice("付款已送出，開通可能需要一點時間，請稍後重新整理。");
            }
          }
        })
        .catch((err) => {
          if (!cancelled) setLoadError(err instanceof Error ? err.message : "讀取訂閱失敗");
        });

    void load();
    if (purchase) setSearchParams({}, { replace: true });
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  return (
    <section className="space-y-4">
      {notice && <p className="rounded-lg border border-border bg-card p-3 text-sm">{notice}</p>}
      {loadError && <p className="text-sm text-destructive">{loadError}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.name}
            plan={plan}
            email={email}
            subscription={subs[plan.route]}
            latest={prices[plan.route]}
            onSaved={(sub) => setSubs((prev) => ({ ...prev, [sub.route]: sub }))}
          />
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        付費訂閱者：每 30 分鐘查一次下個月的最低票價，達到目標價就寄 email 到 {email}。
      </p>
    </section>
  );
}
