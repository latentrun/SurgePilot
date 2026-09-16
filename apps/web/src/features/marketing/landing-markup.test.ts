import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  getStitchLandingMarkup,
  STITCH_LANDING_LINKS,
} from "./pages/stitch-landing-markup";

const logoUrl = "/assets/surgepilot-logo.svg";

function renderLandingDocument() {
  const markup = getStitchLandingMarkup(logoUrl);
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<main>${markup}</main>`, "text/html");
  return { doc, markup };
}

function extractAiLoopSection(source: string) {
  const marker = source.indexOf("AI Engineering Prototype");
  const start = source.lastIndexOf("<section", marker);
  const closingTag = "</section>";
  const end = source.indexOf(closingTag, marker) + closingTag.length;

  expect(marker).toBeGreaterThan(-1);
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
}

function extractDistributedMeshSection(source: string) {
  const start = source.indexOf(
    '<section class="py-24 px-6 max-w-7xl mx-auto overflow-hidden">',
  );
  const end = source.indexOf(
    '\n\n<section class="py-24 px-6 max-w-6xl mx-auto text-center relative">',
    start,
  );

  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  return source
    .slice(start, end)
    .replace(
      /<br\/><span class="font-technical text-\[10px\] uppercase tracking-wider text-on-surface-variant\/60">UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA<\/span>/,
      "",
    );
}

describe("marketing landing static markup", () => {
  it("activates the approved public destinations while preserving product authentication actions", () => {
    const { doc } = renderLandingDocument();

    expect(
      doc.querySelectorAll(`a[href="${STITCH_LANDING_LINKS.docs}"]`),
    ).toHaveLength(2);
    expect(
      doc.querySelectorAll(`a[href="${STITCH_LANDING_LINKS.repository}"]`),
    ).toHaveLength(4);
    expect(
      doc.querySelector(
        `a[href="${STITCH_LANDING_LINKS.repository}#built-100-by-ai"]`,
      ),
    ).not.toBeNull();
    expect(
      doc.querySelector(`a[href="${STITCH_LANDING_LINKS.releases}"]`),
    ).not.toBeNull();
    expect(doc.querySelector('a[href="/login"]')?.textContent).toContain(
      "Log in",
    );
    expect(doc.querySelectorAll('a[href="/register"]')).toHaveLength(3);
    expect(doc.querySelector('a[href="#product"]')).not.toBeNull();
    expect(doc.querySelector('a[href="#how-it-works"]')).not.toBeNull();
    expect(doc.querySelector('a[href$="/SECURITY.md"]')).toBeNull();
    expect(
      doc.querySelector(".marketing-disabled-inline")?.textContent,
    ).toBe("Security");
  });

  it("defers secondary status badges until wide screens so tablet navigation remains readable", () => {
    const { doc } = renderLandingDocument();
    const aiBadge = Array.from(doc.querySelectorAll("span")).find((element) =>
      element.textContent?.includes("100% AI-built"),
    )?.parentElement;
    const sourceBadge = Array.from(doc.querySelectorAll("span")).find(
      (element) => element.textContent?.trim() === "OPEN SOURCE · SELF-HOSTED",
    )?.parentElement;

    expect(aiBadge?.className).toContain("hidden xl:flex");
    expect(sourceBadge?.className).toContain("hidden xl:flex");
  });

  it("restores the original animated dashboard while labelling it as non-benchmark demonstration data", () => {
    const { doc, markup } = renderLandingDocument();

    expect(markup).toContain("OPEN SOURCE · SELF-HOSTED");
    expect(markup).toContain("ANALYTICS_DASHBOARD_LIVE");
    expect(markup).toContain("UI DEMONSTRATION · NOT BENCHMARK DATA");
    expect(markup).toContain("NOT A LIVE SERVICE");
    expect(markup).toContain("8600");
    expect(markup).toContain("REQ/SEC");
    expect(markup).toContain("Active VUs");
    expect(markup).toContain("Global Error Rate");
    expect(doc.querySelector('.counter[data-target="8600"]')).not.toBeNull();
    expect(doc.querySelector(".counter-fast")?.textContent).toBe("1,245");
  });

  it("retains the product landing composition and signature motion markers", () => {
    const { doc, markup } = renderLandingDocument();
    const orderedMarkers = [
      "A distributed load-testing platform",
      "How it was built.",
      "AI Engineering Prototype",
      "Loop Engineering",
      "Command every request.",
      "Recent Test Runs",
      "Distributed load mesh",
      "Ready in four steps.",
      "Inspect the baseline.",
    ];

    let previousIndex = -1;
    for (const marker of orderedMarkers) {
      const index = markup.indexOf(marker);
      expect(index, `missing marker: ${marker}`).toBeGreaterThan(-1);
      expect(index, `marker out of order: ${marker}`).toBeGreaterThan(
        previousIndex,
      );
      previousIndex = index;
    }

    expect(doc.querySelector(".stream-bg")).not.toBeNull();
    expect(doc.querySelector(".orbit-ring")).not.toBeNull();
    expect(doc.querySelector(".orbit-ring-rev")).not.toBeNull();
    expect(doc.querySelectorAll("animateMotion")).toHaveLength(3);
    expect(doc.querySelectorAll(".node-card")).toHaveLength(6);
    expect(doc.querySelectorAll(".reveal-on-scroll")).toHaveLength(4);
    expect(doc.querySelector(".marketing-landing")).toBeNull();
  });

  it("restores the original animated distributed load mesh as a labelled UI demonstration", () => {
    const { doc, markup } = renderLandingDocument();

    for (let node = 1; node <= 6; node += 1) {
      expect(markup).toContain(`node-${String(node).padStart(2, "0")}`);
    }
    for (const marker of [
      "CPU 82%",
      "RAM 14.1G",
    ]) {
      expect(markup).toContain(marker);
    }

    expect(doc.querySelectorAll("animateMotion")).toHaveLength(3);
    expect(doc.querySelectorAll(".node-card")).toHaveLength(6);
    expect(doc.querySelectorAll(".mesh-link")).toHaveLength(6);
    expect(doc.querySelectorAll(".mesh-interface")).toHaveLength(6);
    expect(doc.querySelectorAll(".mesh-packet")).toHaveLength(3);
    expect(doc.querySelectorAll(".mesh-node--pulse")).toHaveLength(3);
    expect(doc.querySelectorAll(".node-card .tooltip")).toHaveLength(0);
    expect(markup).toContain(">BUSY</span>");
    expect(markup).toContain(">IDLE</span>");
    expect(markup).toContain(
      "UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA",
    );
    expect(markup).not.toMatch(/AUTHORITY|RECOVERY|ARTIFACTS|OBSERVE/);
  });

  it("states the exact human and AI responsibility boundary next to the authorship claim", () => {
    const { markup } = renderLandingDocument();

    expect(markup).toContain("The original baseline —");
    expect(markup).toContain("produced by AI agents.");
    expect(markup).toContain(
      "product intent, requirements discussion, product use, usage feedback, and result acceptance",
    );
    expect(markup).toContain(
      "product and process design, governance, quality gates, specifications, architecture, implementation, tests, verification repair, deployment, and release assets",
    );
    expect(markup).toContain("AI Verification &amp; Release");
    expect(markup).not.toContain("Human Review");
  });

  it("restores the original eight-row Recent Test Runs demonstration", () => {
    const { doc, markup } = renderLandingDocument();
    const rows = Array.from(doc.querySelectorAll("[data-run-row]"));

    expect(doc.body.textContent).toContain("Recent Test Runs");
    expect(doc.body.textContent).toContain("LIVE_UPDATE: ON");
    expect(markup).toContain(
      "UI DEMONSTRATION · NOT BENCHMARK DATA · EXAMPLE DATA · NOT A LIVE SERVICE · LIVE_UPDATE: ON",
    );
    expect(rows).toHaveLength(8);
    expect(rows[0]?.textContent).toContain("#SP-9482");
    expect(rows[7]?.textContent).toContain("#SP-9475");
    expect(doc.querySelectorAll("[data-evidence-row]")).toHaveLength(0);
  });

  it("keeps the complete AI and Loop Engineering section identical to the public landing", () => {
    const productSource = readFileSync(
      "src/features/marketing/pages/stitch-landing-markup.ts",
      "utf8",
    );
    const publicSource = readFileSync(
      "../../docs/site/.vitepress/theme/marketing/marketing-markup.ts",
      "utf8",
    );

    expect(extractAiLoopSection(publicSource)).toBe(
      extractAiLoopSection(productSource),
    );
  });

  it("keeps the complete distributed load mesh section identical to the public landing", () => {
    const productSource = readFileSync(
      "src/features/marketing/pages/stitch-landing-markup.ts",
      "utf8",
    );
    const publicSource = readFileSync(
      "../../docs/site/.vitepress/theme/marketing/marketing-markup.ts",
      "utf8",
    );

    expect(extractDistributedMeshSection(publicSource)).toBe(
      extractDistributedMeshSection(productSource),
    );
  });

  it("uses the local logo and no scripts or remote design dependencies", () => {
    const { doc, markup } = renderLandingDocument();

    expect(markup).not.toMatch(/__SURGEPILOT_[A-Z_]+__/);
    expect(markup).not.toMatch(/<script\b/i);
    expect(markup).not.toMatch(
      /tailwindcdn|cdn\.tailwind|fonts\.googleapis|material symbols|googleusercontent/i,
    );

    const images = Array.from(doc.querySelectorAll<HTMLImageElement>("img"));
    expect(images.length).toBeGreaterThanOrEqual(3);
    for (const image of images) {
      expect(image.getAttribute("src")).toBe(logoUrl);
    }
  });

  it("keeps the landing motion active without a reduced-motion override", () => {
    const css = readFileSync(
      "src/features/marketing/pages/landing.css",
      "utf8",
    );

    expect(css).not.toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).not.toMatch(/animation-duration:\s*0\.01ms/);
  });
});
