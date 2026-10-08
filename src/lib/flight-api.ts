// Browser calls go to API Gateway only; the browser never holds AWS credentials.
// The URL is public (no secret), so it falls back to the deployed endpoint when the env var is unset.
const API_BASE = (
  import.meta.env["VITE_FLIGHT_API_URL"] ?? "https://upsjva3kv8.execute-api.us-east-1.amazonaws.com"
).replace(/\/$/, "");

export type PlanName = "tokyo" | "seoul";

export interface Subscription {
  email: string;
  route: string;
  plan_name: PlanName;
  target_price: number;
  currency: "TWD";
  created_at?: string;
  updated_at?: string;
}

export async function listSubscriptions(email: string): Promise<Subscription[]> {
  const res = await fetch(`${API_BASE}/subscriptions?email=${encodeURIComponent(email)}`);
  if (!res.ok) throw new Error(`讀取訂閱失敗（${res.status}）`);
  const data = (await res.json()) as { items: Subscription[] };
  return data.items;
}

export async function saveSubscription(email: string, planName: PlanName, targetPrice: number) {
  const res = await fetch(`${API_BASE}/subscribe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, plan_name: planName, target_price: targetPrice }),
  });
  const data = (await res.json().catch(() => ({}))) as { error?: string };
  if (!res.ok) throw new Error(data.error ?? `訂閱失敗（${res.status}）`);
}
