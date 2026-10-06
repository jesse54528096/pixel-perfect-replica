import { AuthForm } from "@/components/AuthForm";
import { usePageMeta } from "@/lib/use-page-meta";

export default function SignIn() {
  usePageMeta({
    title: "Sign in — Flight Price Notifier",
    description: "Sign in to manage your flight price alerts.",
    ogTitle: "Sign in — Flight Price Notifier",
    ogDescription: "Sign in to manage your flight price alerts.",
  });
  return <AuthForm mode="signin" />;
}
