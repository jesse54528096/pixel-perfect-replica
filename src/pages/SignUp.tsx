import { AuthForm } from "@/components/AuthForm";
import { usePageMeta } from "@/lib/use-page-meta";

export default function SignUp() {
  usePageMeta({
    title: "Sign up — Flight Price Notifier",
    description: "Create an account and get emailed when fares drop below your target.",
    ogTitle: "Sign up — Flight Price Notifier",
    ogDescription: "Create an account and get emailed when fares drop below your target.",
  });
  return <AuthForm mode="signup" />;
}
