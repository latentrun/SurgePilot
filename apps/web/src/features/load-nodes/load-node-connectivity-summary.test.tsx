import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { LoadNodeConnectivitySummary } from "../../app/api-client";
import { LoadNodeConnectivitySummaryCard } from "./components/load-node-connectivity-summary";

function summary(
  overrides: Partial<LoadNodeConnectivitySummary> = {},
): LoadNodeConnectivitySummary {
  return {
    source: "configured",
    readiness: "ready",
    effectiveUrl: "http://10.0.0.5:8080",
    message: "Load Node API Base URL is configured.",
    ...overrides,
  };
}

afterEach(cleanup);

describe("P2-02 Load Node connectivity summary card", () => {
  it("renders the configured origin and readiness without a warning", () => {
    render(<LoadNodeConnectivitySummaryCard isAdmin summary={summary()} />);

    expect(
      screen.getByRole("heading", { name: "Load Node API" }),
    ).toBeInTheDocument();
    expect(screen.getByText("configured")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("http://10.0.0.5:8080")).toBeInTheDocument();
    expect(
      screen.queryByText(/future remote runs will be blocked/i),
    ).not.toBeInTheDocument();
  });

  it("warns admins and links to System Settings for an invalid origin", () => {
    render(
      <LoadNodeConnectivitySummaryCard
        isAdmin
        summary={summary({
          source: "env_fallback",
          readiness: "invalid",
          effectiveUrl: "http://localhost:8000",
        })}
      />,
    );

    expect(screen.getByText("env fallback")).toBeInTheDocument();
    expect(screen.getByText("invalid")).toBeInTheDocument();
    expect(screen.getByText("http://localhost:8000")).toBeInTheDocument();
    expect(
      screen.getByText(/future remote runs will be blocked/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open System Settings" }),
    ).toHaveAttribute("href", "/admin/system-settings");
  });

  it("tells non-admins to contact an administrator for a missing origin", () => {
    render(
      <LoadNodeConnectivitySummaryCard
        isAdmin={false}
        summary={summary({
          source: "missing",
          readiness: "missing",
          effectiveUrl: null,
          message: "Load Node API Base URL is not configured.",
        })}
      />,
    );

    expect(screen.getAllByText("missing")).toHaveLength(2);
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(
      screen.getByText("Contact an administrator to update System Settings."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Open System Settings" }),
    ).not.toBeInTheDocument();
  });

  it("fails closed with a warning when the summary cannot be loaded", () => {
    render(<LoadNodeConnectivitySummaryCard isAdmin loadFailed />);

    expect(
      screen.getByText("Connectivity summary could not be loaded."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Initialization can continue; run start will still validate the current server setting.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/future remote runs will be blocked/i),
    ).toBeInTheDocument();
  });

  it("explains that initialization does not depend on this URL", () => {
    render(
      <LoadNodeConnectivitySummaryCard
        isAdmin
        successContext
        summary={summary()}
      />,
    );

    expect(
      screen.getByText(
        "Initialization does not use this URL. Fixing this URL later does not require reinitializing the node.",
      ),
    ).toBeInTheDocument();
  });
});
