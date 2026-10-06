import { createFileRoute } from "@tanstack/react-router";
import { AuthForm } from "@/components/AuthForm";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Sign up — Flight Price Notifier" },
      { name: "description", content: "Create an account and get emailed when fares drop below your target." },
      { property: "og:title", content: "Sign up — Flight Price Notifier" },
      { property: "og:description", content: "Create an account and get emailed when fares drop below your target." },
    ],
  }),
  component: () => <AuthForm mode="signup" />,
});
