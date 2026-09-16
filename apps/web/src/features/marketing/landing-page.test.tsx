import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LandingPage } from "./pages/landing-page";
import { getStitchLandingMarkup } from "./pages/stitch-landing-markup";

type MockAuthSession = {
  clearPostLogoutRedirect: () => void;
  isAuthenticated: boolean;
  isRestoring: boolean;
  postLogoutRedirectPath: "/" | null;
};

const mockAuthSession = vi.hoisted(() => ({
  current: {
    clearPostLogoutRedirect: vi.fn(),
    isAuthenticated: false,
    isRestoring: false,
    postLogoutRedirectPath: "/" as "/" | null,
  } satisfies MockAuthSession,
}));

vi.mock("../../app/auth-session", () => ({
  useAuthSession: () => mockAuthSession.current,
}));

describe("marketing landing page effects", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
    mockAuthSession.current = {
      clearPostLogoutRedirect: vi.fn(),
      isAuthenticated: false,
      isRestoring: false,
      postLogoutRedirectPath: "/",
    };
  });

  it("reactivates the current injected markup after the post-logout cleanup rerender", async () => {
    vi.useFakeTimers();
    const { container, rerender } = render(<LandingPage />);

    screen.getByRole("heading", {
      name: "A distributed load-testing platform built 100% by AI agents.",
    });
    expect(
      mockAuthSession.current.clearPostLogoutRedirect,
    ).toHaveBeenCalledTimes(1);

    const root = container.querySelector<HTMLElement>(".marketing-landing");
    expect(root).not.toBeNull();
    expect(
      screen.getByText("1. Design").closest(".reveal-on-scroll"),
    ).toHaveClass("active");

    root!.innerHTML = getStitchLandingMarkup("/assets/surgepilot-logo.svg");
    expect(
      screen.getByText("1. Design").closest(".reveal-on-scroll"),
    ).not.toHaveClass("active");

    mockAuthSession.current = {
      ...mockAuthSession.current,
      postLogoutRedirectPath: null,
    };
    rerender(<LandingPage />);

    expect(
      screen.getByText("1. Design").closest(".reveal-on-scroll"),
    ).toHaveClass("active");
    const throughput = root!.querySelector<HTMLElement>(
      '.counter[data-target="8600"]',
    );
    const activeVus = root!.querySelector<HTMLElement>(".counter-fast");
    expect(throughput?.textContent).toBe("0");
    expect(activeVus?.textContent).toBe("1,245");
    act(() => vi.advanceTimersByTime(50));
    expect(throughput?.textContent).toBe("215");
    expect(activeVus?.textContent).toBe("1,249");
    expect(
      screen.getByText(
        /ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();
  });
});
