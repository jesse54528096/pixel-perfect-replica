// Browser calls go to API Gateway only; the browser never holds AWS credentials.
// The URL is public (no secret), so it falls back to the deployed endpoint when the env var is unset.
const API_BASE = (
  import.meta.env["VITE_FLIGHT_API_URL"] ?? "https://upsjva3kv8.execute-api.us-east-1.amazonaws.com"
).replace(/\/$/, "");

export type PlanName = "tokyo" | "seoul";

export type SubscriptionStatus = "pending_payment" | "active" | "cancelled" | "expired";

export interface Subscription {
  email: string;
  route: string;
  plan_name: PlanName;
  target_price: number;
  currency: "TWD";
  // Rows saved before payments existed have no status; treat them as unpaid.
  subscription_status?: SubscriptionStatus;
  current_period_end?: string;
  current_period_end_date?: string;
  created_at?: string;
  updated_at?: string;
}

export async function listSubscriptions(email: string): Promise<Subscription[]> {
  const res = await fetch(`${API_BASE}/subscriptions?email=${encodeURIComponent(email)}`);
  if (!res.ok) throw new Error(`讀取訂閱失敗（${res.status}）`);
  const data = (await res.json()) as { items: Subscription[] };
  return data.items;
}

// Unpaid plans get an ECPay checkout page (HTML) that redirects the browser to pay.
// Paid plans (or cancelled ones still inside the paid period) get JSON: the target price was updated in place.
export async function saveSubscription(
  email: string,
  planName: PlanName,
  targetPrice: number,
): Promise<{ redirected: true } | { redirected: false; subscription: Subscription }> {
  const res = await fetch(`${API_BASE}/subscribe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, plan_name: planName, target_price: targetPrice }),
  });
  if (res.ok && (res.headers.get("content-type") ?? "").includes("text/html")) {
    const html = await res.text();
    document.open();
    document.write(html);
    document.close();
    return { redirected: true };
  }
  const data = (await res.json().catch(() => ({}))) as Partial<Subscription> & { error?: string };
  if (!res.ok) throw new Error(data.error ?? `訂閱失敗（${res.status}）`);
  return { redirected: false, subscription: data as Subscription };
}

export async function cancelSubscription(email: string, route: string, accessToken: string) {
  const res = await fetch(`${API_BASE}/cancel`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ email, route }),
  });
  const data = (await res.json().catch(() => ({}))) as {
    error?: string;
    current_period_end?: string;
    current_period_end_date?: string;
  };
  if (!res.ok) throw new Error(data.error ?? `取消失敗（${res.status}）`);
  return data;
}

export interface LatestPrice {
  route: string;
  month: string;
  price: number;
  currency: "TWD";
  airline: string | null;
  price_usd: number | null;
  checked_at: string;
}

export async function listLatestPrices(): Promise<LatestPrice[]> {
  const res = await fetch(`${API_BASE}/prices`);
  if (!res.ok) throw new Error(`讀取票價失敗（${res.status}）`);
  const data = (await res.json()) as { items: LatestPrice[] };
  return data.items;
}
