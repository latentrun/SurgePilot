import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";

const pageNames = [
  "index",
  "quickstart",
  "startup-modes",
  "configuration",
  "first-run",
  "faq",
];
const locales = [
  { prefix: "docs/", homeLabel: "Documentation Home" },
  { prefix: "docs/zh-CN/", homeLabel: "文档首页" },
  { prefix: "docs/ja/", homeLabel: "ドキュメントホーム" },
];
const siteUrl = new URL(
  process.env.SURGEPILOT_PUBLIC_SITE_URL ??
    "https://latentrun.github.io/SurgePilot/",
);
const attempts = Number(process.env.SURGEPILOT_LIVE_SMOKE_ATTEMPTS ?? "30");
const retryDelayMs = Number(
  process.env.SURGEPILOT_LIVE_SMOKE_RETRY_DELAY_MS ?? "2000",
);

if (!siteUrl.pathname.endsWith("/")) {
  siteUrl.pathname += "/";
}
assert.ok(Number.isInteger(attempts) && attempts > 0, "attempts must be a positive integer");
assert.ok(
  Number.isFinite(retryDelayMs) && retryDelayMs >= 0,
  "retry delay must be a non-negative number",
);

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function fetchHtml(route) {
  const url = new URL(route, siteUrl);
  const response = await fetch(url, {
    headers: { "cache-control": "no-cache" },
  });
  assert.equal(response.status, 200, `${url} returned ${response.status}`);
  return { html: await response.text(), url };
}

function verifyDocsNavigation(html, url, locale) {
  const projectBase = siteUrl.pathname;
  const brandPattern = new RegExp(
    `<a\\b(?=[^>]*class="title")(?=[^>]*href="${escapeRegExp(projectBase)}")[^>]*>`,
  );
  assert.match(html, brandPattern, `${url} is missing the marketing-home brand link`);

  const docsHome = `${projectBase}${locale.prefix}`;
  const docsHomePattern = new RegExp(
    `<a\\b(?=[^>]*href="${escapeRegExp(docsHome)}")[^>]*>` +
      `[\\s\\S]*?<span\\b[^>]*>${escapeRegExp(locale.homeLabel)}</span>` +
      `[\\s\\S]*?</a>`,
  );
  assert.match(
    html,
    docsHomePattern,
    `${url} is missing the localized documentation-home link`,
  );
}

async function verifyDeployedSite() {
  const marketing = await fetchHtml("");
  assert.match(
    marketing.html,
    /data-marketing-home/,
    `${marketing.url} is not the SurgePilot marketing homepage`,
  );

  await Promise.all(
    locales.flatMap((locale) =>
      pageNames.map(async (pageName) => {
        const route = `${locale.prefix}${pageName === "index" ? "" : pageName}`;
        const page = await fetchHtml(route);
        verifyDocsNavigation(page.html, page.url, locale);
      }),
    ),
  );
}

let lastError;
for (let attempt = 1; attempt <= attempts; attempt += 1) {
  try {
    await verifyDeployedSite();
    console.log(`Verified deployed navigation for ${siteUrl}`);
    process.exitCode = 0;
    lastError = undefined;
    break;
  } catch (error) {
    lastError = error;
    if (attempt < attempts) {
      await delay(retryDelayMs);
    }
  }
}

if (lastError) {
  throw lastError;
}
