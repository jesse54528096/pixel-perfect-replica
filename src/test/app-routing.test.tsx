import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "@/App";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App routing", () => {
  it("renders the landing page at /", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1, name: "Flight Price Notifier" })).toBeInTheDocument();
  });

  it("renders the sign-in and sign-up pages", () => {
    renderAt("/signin");
    expect(screen.getByRole("heading", { name: /Sign in \/ 登入/ })).toBeInTheDocument();
  });

  it("falls back to 404 for unknown paths", () => {
    renderAt("/nope");
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });
});
