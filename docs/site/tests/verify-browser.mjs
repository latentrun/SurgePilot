import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

import { chromium } from "@playwright/test";

const port = Number(process.env.SURGEPILOT_DOCS_PREVIEW_PORT ?? "4178");
const baseUrl = `http://127.0.0.1:${port}/SurgePilot/`;
const publicOrigin = "https://latentrun.github.io";
const publicBase = "/SurgePilot/";

const preview = spawn(
  process.platform === "win32" ? "pnpm.cmd" : "pnpm",
  ["exec", "vitepress", "preview", "--host", "127.0.0.1", "--port", String(port)],
  { stdio: "inherit" },
);
let previewError = null;
preview.once("error", (error) => {
  previewError = error;
});

function stopPreview() {
  if (!preview.killed) {
    preview.kill("SIGTERM");
  }
}

process.once("exit", stopPreview);
process.once("SIGINT", () => {
  stopPreview();
  process.exit(130);
});
process.once("SIGTERM", () => {
  stopPreview();
  process.exit(143);
});

async function waitForPreview() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (previewError) {
      throw previewError;
    }
    if (preview.exitCode !== null) {
      throw new Error(`VitePress preview exited before readiness (code ${preview.exitCode})`);
    }
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The preview process may need another polling interval to start.
    }
    await delay(250);
  }
  throw new Error(`VitePress preview did not become ready at ${baseUrl}`);
}

function absoluteUrl(route) {
  return `${publicOrigin}${publicBase}${route.replace(/^\/+/, "")}`;
}

await waitForPreview();

const browserLaunchOptions = {
  headless: true,
  args: ["--no-sandbox"],
};
if (process.env.CHROME_PATH) {
  browserLaunchOptions.executablePath = process.env.CHROME_PATH;
}
const browser = await chromium.launch(browserLaunchOptions);
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error));

await page.goto(baseUrl, { waitUntil: "networkidle" });
assert.equal(
  await page.title(),
  "SurgePilot: 100% AI-Built Distributed Load Testing",
);
assert.equal(await page.locator("h1").count(), 1);
assert.equal(await page.locator("[data-marketing-home]").count(), 1);
assert.equal(
  await page.locator("link[rel=canonical]").getAttribute("href"),
  absoluteUrl(""),
);
assert.match(
  await page.locator("main").innerText(),
  /ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA · EXAMPLE DATA · NOT A LIVE SERVICE/,
);
const marketingSchema = JSON.parse(
  await page.locator('script[type="application/ld+json"]').first().textContent(),
);
assert.deepEqual(
  marketingSchema["@graph"].map((node) => node["@type"]),
  ["WebSite", "SoftwareApplication"],
);

await page.goto(`${baseUrl}docs/`, { waitUntil: "networkidle" });
assert.equal(await page.title(), "SurgePilot Documentation: Install, Configure, and Run");
assert.equal(await page.locator("h1").count(), 1);
assert.equal(
  await page.locator("link[rel=canonical]").getAttribute("href"),
  absoluteUrl("docs/"),
);
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "networkidle" });
assert.equal(
  await page.locator("html").evaluate((element) => element.classList.contains("dark")),
  true,
  "the docs home must default to dark mode without a saved appearance preference",
);
assert.equal(await page.locator('link[rel="alternate"][hreflang="zh-CN"]').count(), 1);
assert.match(await page.locator("#VPContent").innerText(), /Core workflow/);
assert.doesNotMatch(await page.locator("#VPContent").innerText(), /Human responsibilities/);
assert.doesNotMatch(await page.locator("#VPContent").innerText(), /Public API AI Skill/);
const docsSchema = JSON.parse(
  await page.locator('script[type="application/ld+json"]').first().textContent(),
);
assert.ok(
  docsSchema["@graph"].some((node) => node["@type"] === "TechArticle"),
);

const brandLink = page.locator(".VPNavBarTitle a.title");
assert.equal(await brandLink.getAttribute("href"), publicBase);
await brandLink.click();
await page.waitForURL(baseUrl);
await page.locator("[data-marketing-home]").waitFor({ state: "visible" });
assert.equal(await page.locator("[data-marketing-home]").count(), 1);

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${baseUrl}docs/ja/quickstart`, { waitUntil: "networkidle" });
await page.locator(".VPNavBarHamburger").click();
const mobileDocsHome = page.locator(".VPNavScreen a", {
  hasText: "ドキュメントホーム",
});
assert.equal(await mobileDocsHome.getAttribute("href"), `${publicBase}docs/ja/`);
await mobileDocsHome.click();
await page.waitForURL(`${baseUrl}docs/ja/`);

assert.deepEqual(pageErrors, [], "public pages must not emit browser page errors");
await browser.close();
stopPreview();

console.log("Verified public metadata and rendered content in a headless browser.");
