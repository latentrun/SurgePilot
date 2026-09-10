import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HttpTrace, Nodes, runReportRefetchInterval } from "./pages/run-report-page";
import type { RunReportDetail } from "../../app/api-client";

describe("Run Report Debug HTTP Trace checkpoint behavior", () => {
  it("renders a sanitized trace for supported Debug Runs", () => {
    const report = {
      verdict: { runType: "debug", sourceType: "debug_scenario" },
      debugHttpTrace: {
        status: "available",
        entryCount: 1,
        traceTruncated: false,
        entries: [{ sequence: 1, label: "Login", method: "GET", url: "https://example.test", requestHeaders: { Authorization: "[REDACTED]" }, requestBody: { contentType: "application/json", text: "{}" }, responseStatus: 200, responseHeaders: {}, responseBody: { contentType: "application/json", text: "{}" }, durationMs: 10, error: null }],
      },
    } as unknown as RunReportDetail;

    render(<HttpTrace report={report} />);
    expect(screen.getByRole("heading", { name: "HTTP Trace" })).toBeTruthy();
    expect(screen.getByText("Authorization: [REDACTED]")).toBeTruthy();
  });

  it("does not render trace for Standard Runs", () => {
    const report = { verdict: { runType: "standard", sourceType: "test_plan" }, debugHttpTrace: null } as unknown as RunReportDetail;
    render(<HttpTrace report={report} />);
    expect(screen.queryByRole("heading", { name: "HTTP Trace" })).toBeNull();
  });

  it("keeps polling active runs and stops after a terminal parsed report", () => {
    const active = {
      verdict: { state: "running" },
      kpiSummary: { status: "pending" },
    } as never;
    const terminal = {
      verdict: { state: "finished" },
      kpiSummary: { status: "parsed" },
    } as never;

    expect(runReportRefetchInterval(active, 0)).toBe(5000);
    expect(runReportRefetchInterval(terminal, 0)).toBe(false);
  });

  it("keeps a terminal report polling while final stats are pending", () => {
    const report = {
      verdict: { state: "failed" },
      kpiSummary: { status: "pending" },
    } as never;

    expect(runReportRefetchInterval(report, 0)).toBe(5000);
    expect(runReportRefetchInterval(report, 12)).toBe(false);
  });

  it("renders allocation-backed node rows without execution internals", () => {
    const report = {
      verdict: { runType: "standard", sourceType: "test_plan", slaResult: "failed" },
      snapshot: {
        resourceRequest: { mode: "manual", poolType: "workspace", expectedConcurrencyPerNode: 20 },
      },
      allocatedNodes: [
        {
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          name: "Load Node A",
          nodeIndex: 1,
          totalNodes: 2,
          state: "finished",
          lastHeartbeatAt: null,
          slaResult: "passed",
          cleanupStatus: "released",
          terminalReason: "finished",
          quarantineReason: null,
        },
      ],
    } as never;

    render(<Nodes report={report} />);

    expect(screen.getByText("Run-level SLA:")).toBeTruthy();
    expect(screen.getByText("Node 1 of 2 · finished")).toBeTruthy();
    expect(screen.getByText("SLA: SLA passed")).toBeTruthy();
    expect(screen.queryByText(/sshUser|runnerHome|private-node|\/opt\//i)).toBeNull();
  });
});
