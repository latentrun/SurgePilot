import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dist = new URL("../.vitepress/dist/", import.meta.url).pathname;
const publicOrigin = "https://latentrun.github.io";
const projectBase = "/SurgePilot/";
const socialImageUrl = `${publicOrigin}${projectBase}surgepilot-architecture.jpg`;
const pageNames = [
  "index",
  "quickstart",
  "startup-modes",
  "configuration",
  "first-run",
  "faq",
];
const pages = [
  {
    file: "index.html",
    route: "/",
    locale: "en",
    slug: null,
    type: "marketing",
  },
];

for (const page of pageNames) {
  const slug = page === "index" ? "" : page;
  pages.push({
    file: join("docs", `${page}.html`),
    route: `/docs/${slug}`,
    locale: "en",
    slug,
    type: "docs",
  });
  pages.push({
    file: join("docs", "zh-CN", `${page}.html`),
    route: `/docs/zh-CN/${slug}`,
    locale: "zh-CN",
    slug,
    type: "docs",
  });
  pages.push({
    file: join("docs", "ja", `${page}.html`),
    route: `/docs/ja/${slug}`,
    locale: "ja",
    slug,
    type: "docs",
  });
}

function canonicalUrl(route) {
  const suffix = route === "/" ? "" : route.replace(/^\//, "");
  return `${publicOrigin}${projectBase}${suffix}`;
}

function tags(html, name) {
  return html.match(new RegExp(`<${name}\\b[^>]*>`, "g")) ?? [];
}

function attributes(tag) {
  return Object.fromEntries(
    [...tag.matchAll(/([:\w-]+)="([^"]*)"/g)].map((match) => [
      match[1],
      match[2],
    ]),
  );
}

function findLink(html, rel, hreflang) {
  return tags(html, "link")
    .map(attributes)
    .find(
      (attrs) =>
        attrs.rel === rel &&
        (hreflang === undefined || attrs.hreflang === hreflang),
    );
}

function findMeta(html, key, value) {
  return tags(html, "meta")
    .map(attributes)
    .find((attrs) => attrs[key] === value)?.content;
}

function jpegDimensions(buffer) {
  assert.equal(buffer[0], 0xff, "social image must be a JPEG");
  assert.equal(buffer[1], 0xd8, "social image must be a JPEG");

  let offset = 2;
  while (offset < buffer.length) {
    while (buffer[offset] === 0xff) offset += 1;
    const marker = buffer[offset];
    offset += 1;

    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    assert.ok(offset + 2 <= buffer.length, "invalid JPEG segment");

    const length = buffer.readUInt16BE(offset);
    const isStartOfFrame =
      (marker >= 0xc0 && marker <= 0xc3) ||
      (marker >= 0xc5 && marker <= 0xc7) ||
      (marker >= 0xc9 && marker <= 0xcb) ||
      (marker >= 0xcd && marker <= 0xcf);
    if (isStartOfFrame) {
      return {
        height: buffer.readUInt16BE(offset + 3),
        width: buffer.readUInt16BE(offset + 5),
      };
    }
    offset += length;
  }

  throw new Error("JPEG dimensions not found");
}

function routeForLocale(locale, slug) {
  const localePrefix = locale === "en" ? "" : `${locale}/`;
  return `/docs/${localePrefix}${slug}`;
}

const titles = new Set();
const descriptions = new Set();
const expectedCanonicals = new Set();

for (const page of pages) {
  const html = readFileSync(join(dist, page.file), "utf8");
  const h1Count = (html.match(/<h1(?:\s|>)/g) ?? []).length;
  assert.equal(h1Count, 1, `${page.file} must contain exactly one h1`);
  assert.doesNotMatch(
    html,
    /(?:href|src)="\/(?!SurgePilot\/)/,
    `${page.file} contains a host-root asset or link`,
  );

  const title = html.match(/<title>([^<]+)<\/title>/)?.[1];
  const description = findMeta(html, "name", "description");
  assert.ok(title, `${page.file} is missing a title`);
  assert.ok(description, `${page.file} is missing a description`);
  assert.ok(!titles.has(title), `${page.file} duplicates title: ${title}`);
  assert.ok(
    !descriptions.has(description),
    `${page.file} duplicates description: ${description}`,
  );
  titles.add(title);
  descriptions.add(description);

  const canonical = canonicalUrl(page.route);
  expectedCanonicals.add(canonical);
  assert.equal(findLink(html, "canonical")?.href, canonical);
  const socialTitle = findMeta(html, "property", "og:title");
  assert.ok(socialTitle, `${page.file} is missing an Open Graph title`);
  assert.ok(
    title.startsWith(socialTitle),
    `${page.file} social title diverges from document title`,
  );
  assert.equal(findMeta(html, "property", "og:description"), description);
  assert.equal(findMeta(html, "property", "og:url"), canonical);
  assert.equal(findMeta(html, "property", "og:image"), socialImageUrl);
  assert.equal(
    findMeta(html, "property", "og:type"),
    page.type === "marketing" ? "website" : "article",
  );
  assert.equal(findMeta(html, "name", "twitter:card"), "summary_large_image");
  assert.equal(findMeta(html, "name", "twitter:title"), socialTitle);
  assert.equal(findMeta(html, "name", "twitter:description"), description);
  assert.equal(findMeta(html, "name", "twitter:image"), socialImageUrl);
  assert.match(findMeta(html, "name", "robots") ?? "", /index,follow/);

  const jsonLdBlocks = [
    ...html.matchAll(
      /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g,
    ),
  ].map((match) => JSON.parse(match[1]));
  assert.ok(jsonLdBlocks.length > 0, `${page.file} is missing JSON-LD`);
  const jsonLdTypes = new Set(
    jsonLdBlocks.flatMap((block) => {
      const nodes = block["@graph"] ?? [block];
      return nodes.flatMap((node) => node["@type"] ?? []);
    }),
  );
  if (page.type === "marketing") {
    assert.ok(jsonLdTypes.has("WebSite"));
    assert.ok(jsonLdTypes.has("SoftwareApplication"));
  } else {
    assert.ok(jsonLdTypes.has("TechArticle"));
    assert.ok(jsonLdTypes.has("BreadcrumbList"));
    for (const locale of ["en", "zh-CN", "ja", "x-default"]) {
      const targetLocale = locale === "x-default" ? "en" : locale;
      const expected = canonicalUrl(routeForLocale(targetLocale, page.slug));
      assert.equal(findLink(html, "alternate", locale)?.href, expected);
    }
    if (page.slug === "") {
      assert.match(html, /src="\/SurgePilot\/surgepilot-hero\.webp"/);
      assert.match(
        html,
        /alt="Illustrative SurgePilot AI load-testing artwork; not a performance benchmark"/,
      );
    }
  }
}

const marketingHtml = readFileSync(join(dist, "index.html"), "utf8");
assert.match(
  marketingHtml,
  /(?:href|src)="\/SurgePilot\//,
  "marketing output must use the GitHub Pages project base",
);
assert.match(marketingHtml, /data-marketing-home/);
for (const marker of [
  "A distributed load-testing platform built 100% by AI agents.",
  "How it was built.",
  "AI Engineering Prototype",
  "Loop Engineering",
  "Command every request.",
  "Distributed load mesh",
  "Ready in four steps.",
  "ANALYTICS_DASHBOARD_LIVE",
  "Recent Test Runs",
  "8600",
  "REQ/SEC",
  "1,245",
  "Global Error Rate",
]) {
  assert.match(
    marketingHtml,
    new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
  );
}
assert.match(marketingHtml, /marketing-landing static-dot-grid/);
assert.doesNotMatch(marketingHtml, /A distributed system built\s*<em>/);
assert.match(
  marketingHtml,
  /Turn API &amp; business flows into[\s\S]*reusable load tests\./,
);
assert.match(
  marketingHtml,
  /<title>SurgePilot: 100% AI-Built Distributed Load Testing<\/title>/,
);
assert.equal(
  marketingHtml.split(
    'href="https://github.com/latentrun/SurgePilot#built-100-by-ai"',
  ).length - 1,
  2,
  "marketing evidence links must target the README Built 100% by AI anchor",
);
assert.match(marketingHtml, /Original public baseline · produced by AI agents/);
assert.match(
  marketingHtml,
  /explicit human\/AI responsibilities and repository-backed evidence/,
  "marketing metadata must qualify the AI-authorship claim with its evidence boundary",
);
assert.match(
  marketingHtml,
  /Human participation is explicit: product intent, requirements discussion/,
);
assert.match(marketingHtml, /AI agents handled product and process design/);
assert.doesNotMatch(
  marketingHtml,
  /842000|12,450/,
  "marketing output must use the approved compact presentation values",
);
for (const disclaimer of [
  "UI DEMONSTRATION",
  "NOT BENCHMARK DATA",
  "EXAMPLE DATA",
  "NOT A LIVE SERVICE",
]) {
  assert.match(
    marketingHtml,
    new RegExp(disclaimer),
    `marketing output must label synthetic UI data: ${disclaimer}`,
  );
}
assert.match(
  marketingHtml,
  /ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA · EXAMPLE DATA · NOT A LIVE SERVICE/,
  "dashboard metrics must carry an adjacent synthetic-data disclaimer",
);
assert.match(
  marketingHtml,
  /Recent Test Runs[\s\S]*?UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA[\s\S]*?LIVE_UPDATE: ON/,
  "recent runs must carry an adjacent synthetic-data disclaimer",
);
assert.match(
  marketingHtml,
  /Distributed load mesh[\s\S]*?UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA/,
  "distributed mesh must carry an adjacent synthetic-data disclaimer",
);
for (const marker of [
  "node-01",
  "node-02",
  "node-03",
  "node-04",
  "node-05",
  "node-06",
  "CPU 82%",
  "RAM 14.1G",
]) {
  assert.match(
    marketingHtml,
    new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
  );
}
assert.equal(
  (marketingHtml.match(/class="node-card /g) ?? []).length,
  6,
  "marketing output must render six distributed node cards",
);
assert.equal(
  (marketingHtml.match(/class="mesh-link /g) ?? []).length,
  6,
  "marketing output must render six mesh links",
);
assert.equal(
  (marketingHtml.match(/class="mesh-interface /g) ?? []).length,
  6,
  "marketing output must render six mesh interface points",
);
assert.equal(
  (marketingHtml.match(/class="node-card[^>]*mesh-node--pulse/g) ?? []).length,
  3,
  "marketing output must pulse the three BUSY mesh nodes",
);
assert.match(
  marketingHtml,
  /<filter id="mesh-link-glow"[^>]*filterUnits="userSpaceOnUse"[^>]*x="-300"[^>]*y="-300"[^>]*width="600"[^>]*height="600"/,
  "horizontal BUSY links must use a non-zero user-space filter region",
);
assert.doesNotMatch(marketingHtml, /AUTHORITY|RECOVERY|ARTIFACTS|OBSERVE/);
assert.doesNotMatch(
  marketingHtml,
  /<h4[^>]*>Live Combined Throughput|<h4[^>]*>Active VUs|<h4[^>]*>Global Error Rate/,
);
assert.match(marketingHtml, /<h2[^>]*>Recent Test Runs<\/h2>/);
assert.ok(
  (marketingHtml.match(/Star on GitHub/g) ?? []).length >= 2,
  "marketing output must repeat the primary Star action",
);
assert.match(
  marketingHtml,
  /href="https:\/\/github\.com\/latentrun\/SurgePilot"/,
);
assert.match(marketingHtml, /href="\/SurgePilot\/docs\/"/);
assert.match(
  marketingHtml,
  /href="https:\/\/github\.com\/latentrun\/SurgePilot\/releases"/,
);
assert.match(marketingHtml, /Inspect the evidence/);
assert.match(marketingHtml, /node-01.*node-02.*node-03.*node-04/s);
assert.doesNotMatch(
  marketingHtml,
  /Log in|Sign up|ALL SYSTEMS OPERATIONAL|pricing/i,
);
assert.equal(
  (marketingHtml.match(/data-run-row/g) ?? []).length,
  8,
  "marketing output must preserve the eight-row Recent Test Runs demonstration",
);
assert.doesNotMatch(marketingHtml, /aria-disabled="true"/);
assert.doesNotMatch(marketingHtml, /surgepilot-hero\.png/);

const sitemap = readFileSync(join(dist, "sitemap.xml"), "utf8");
const sitemapUrls = new Set(
  [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]),
);
assert.deepEqual(sitemapUrls, expectedCanonicals);

const robots = readFileSync(join(dist, "robots.txt"), "utf8");
assert.match(robots, /^User-agent: \*$/m);
assert.match(robots, /^Allow: \/SurgePilot\/$/m);
assert.match(
  robots,
  /^Sitemap: https:\/\/latentrun\.github\.io\/SurgePilot\/sitemap\.xml$/m,
);
assert.doesNotMatch(robots, /^Disallow:/m);

const notFound = readFileSync(join(dist, "404.html"), "utf8");
assert.match(findMeta(notFound, "name", "robots") ?? "", /noindex,nofollow/);
assert.equal(findLink(notFound, "canonical"), undefined);

const socialImage = readFileSync(join(dist, "surgepilot-architecture.jpg"));
const socialImageDimensions = jpegDimensions(socialImage);
assert.equal(socialImageDimensions.width, 1200);
assert.equal(socialImageDimensions.height, 630);
assert.ok(socialImage.length <= 250_000, "social image exceeds 250 KB");

const docsHero = readFileSync(join(dist, "surgepilot-hero.webp"));
assert.equal(docsHero.subarray(0, 4).toString("ascii"), "RIFF");
assert.equal(docsHero.subarray(8, 12).toString("ascii"), "WEBP");
assert.ok(docsHero.length <= 250_000, "documentation hero exceeds 250 KB");
assert.ok(!readdirSync(dist).includes("surgepilot-hero.png"));

function walkFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walkFiles(path) : [path];
  });
}

const builtFiles = walkFiles(dist);
const marketingComponent = readFileSync(
  new URL("../.vitepress/theme/MarketingHome.vue", import.meta.url),
  "utf8",
);
const marketingCss = readFileSync(
  new URL("../.vitepress/theme/marketing/marketing.css", import.meta.url),
  "utf8",
);
assert.doesNotMatch(marketingComponent, /prefers-reduced-motion|motion-ready/);
assert.doesNotMatch(marketingCss, /prefers-reduced-motion:\s*reduce/);
assert.match(
  marketingCss,
  /\.marketing-landing \.text-\\\[10px\\\]\s*\{[^}]*line-height:\s*1\.5/s,
  "public marketing technical labels must match the product Landing line height",
);
assert.match(
  marketingCss,
  /\.marketing-landing \.blur-\\\[100px\\\]\s*\{[^}]*filter:\s*blur\(100px\)/s,
  "public Loop Engineering glows must match the product blur utility",
);
assert.match(
  marketingCss,
  /\.marketing-landing \.border\s*\{[^}]*border-width:\s*1px[^}]*border-style:\s*solid/s,
  "public marketing borders must match the product Landing utilities",
);
const builtBytes = builtFiles.reduce(
  (total, file) => total + statSync(file).size,
  0,
);
assert.ok(builtBytes <= 3_000_000, `built site exceeds 3 MB: ${builtBytes}`);
for (const file of builtFiles.filter((path) =>
  /\.(?:css|js|ttf|woff2)$/.test(path),
)) {
  assert.ok(
    statSync(file).size <= 150_000,
    `${file} exceeds the 150 KB emitted-asset budget`,
  );
}

console.log(
  `Verified ${pages.length} public-site pages and ${builtFiles.length} assets.`,
);
