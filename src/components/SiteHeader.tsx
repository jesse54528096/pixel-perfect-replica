import { Link } from "@tanstack/react-router";
import { Plane } from "lucide-react";
import type { ReactNode } from "react";

export function SiteHeader({ right }: { right?: ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/70 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow-glow">
            <Plane className="h-4 w-4" />
          </span>
          Flight Price Notifier
        </Link>
        {right}
      </div>
    </header>
  );
}
