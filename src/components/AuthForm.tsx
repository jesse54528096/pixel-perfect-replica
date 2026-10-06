import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SiteHeader } from "@/components/SiteHeader";

export function AuthForm({ mode }: { mode: "signin" | "signup" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isSignup = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { data, error } = isSignup
      ? await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + "/app" } })
      : await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) return setError(error.message);
    if (data.session) navigate({ to: "/app" });
    else setError("Check your email to confirm your account.");
  }

  return (
    <div className="flex min-h-screen flex-col bg-hero">
      <SiteHeader />
      <main className="flex flex-1 items-center justify-center px-5 py-16">
        <form onSubmit={onSubmit} className="animate-fade-up w-full max-w-sm space-y-5 rounded-2xl border border-border bg-card p-8">
          <div>
            <h1 className="text-2xl font-bold">{isSignup ? "Create account / 註冊" : "Sign in / 登入"}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {isSignup ? "Start watching fares in seconds." : "Welcome back."}
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "…" : isSignup ? "Sign up" : "Sign in"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            {isSignup ? (
              <>Already have an account? <Link to="/signin" className="text-primary hover:underline">Sign in</Link></>
            ) : (
              <>No account yet? <Link to="/signup" className="text-primary hover:underline">Sign up</Link></>
            )}
          </p>
        </form>
      </main>
    </div>
  );
}
