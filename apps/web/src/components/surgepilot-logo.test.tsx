import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SurgePilotLogo } from "./surgepilot-logo";

afterEach(() => {
  cleanup();
});

describe("SurgePilotLogo", () => {
  it("exposes accessible alt text by default", () => {
    render(<SurgePilotLogo />);

    const logo = screen.getByRole("img", { name: "SurgePilot logo" });
    expect(logo).toHaveAttribute("alt", "SurgePilot logo");
    expect(logo.getAttribute("src")).toContain("image/svg+xml");
  });

  it("is hidden from assistive technology when decorative", () => {
    const { container } = render(<SurgePilotLogo decorative className="custom-logo" />);

    const logo = container.querySelector("img");
    expect(logo).toHaveAttribute("alt", "");
    expect(logo).toHaveAttribute("aria-hidden", "true");
    expect(logo).toHaveClass("custom-logo");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
