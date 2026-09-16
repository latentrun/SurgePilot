# P2-07 Public Launch, GitHub Pages, and SEO

- Document status: Active through `ADR-0026`; implementation authorized within this Slice
- Phase: P2
- Capability: `public_launch_github_pages_seo`
- Activation ADR: `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- Approved proposal: `docs/sdd/public-launch-github-pages-and-star-growth-plan.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`
- Repository workflow: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Product Marketing Landing boundary: `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`
- Documentation localization boundary:
  `docs/sdd/adr/ADR-0025-public-user-documentation-localization.md`
- Release boundaries: `docs/sdd/slices/P2-05-cross-platform-distribution.md` and
  `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Frontend boundary: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing boundary: `docs/sdd/09-testing-and-acceptance-strategy.md`

## 1. Core Decision

P2-07 activates one bounded public-launch surface for `latentrun/SurgePilot`:

```text
one VitePress build under docs/site
  -> static AI-first marketing homepage at /SurgePilot/
  -> English user docs at /SurgePilot/docs/
  -> Simplified Chinese docs at /SurgePilot/docs/zh-CN/
  -> Japanese docs at /SurgePilot/docs/ja/
  -> one canonical/sitemap/hreflang/metadata system
```

The public site exists to make the repository discoverable, explain the original AI-authored
baseline accurately, prove that SurgePilot is a real distributed system, and convert interested
technical visitors into legitimate GitHub Stars.

P2-07 keeps the public Pages marketing implementation separate from the self-hosted React product
Landing. It consumes the already-authorized tagged Release and does not change Runtime distribution
behavior. Its only self-hosted Landing changes are the exact public Docs/repository targets and the
explicitly labelled synthetic UI demonstration authorized by ADR-0026; authentication, routing,
APIs, and product capability remain unchanged.

## 2. Goals

1. Publish the repository, GitHub Pages marketing homepage, localized documentation, and an
   installable tagged Release as one coordinated launch.
2. Use the original AI-authored baseline as the primary attention hook while defining the human
   and AI responsibilities precisely.
3. Provide repository-backed evidence that the result is a real distributed system rather than a
   generated frontend demo.
4. Produce static, crawlable, shareable Pages output with complete publication metadata.
5. Keep all self-hosted product Web routes out of search indexes by default.
6. Preserve the exact six-page English/`zh-CN`/`ja` user-guide mirrors and operational contract
   checks while moving them below `/docs/`.
7. Prepare launch video, social images, README, repository metadata, and public-readiness checks
   while the repository remains private.
8. Allow ordinary human- or AI-authored community contribution after the original baseline.

## 3. Non-goals

P2-07 must not implement:

1. hosted SurgePilot, public user registration, pricing, billing, leads, newsletter, or analytics
   product features;
2. blog/CMS, programmatic SEO, automated articles, multi-version documentation, automatic
   translation, or browser/IP language redirects;
3. a custom domain for the initial launch;
4. product UI or API-message localization;
5. publication of private Codex sessions;
6. mandatory AI-generation proof for future community contributions;
7. new API routes, contracts, database tables, migrations, services, queues, or storage;
8. changes to Runner, Run state, Load Node, Runtime, Compose, installer, or release integrity;
9. a cross-app UI library or shared marketing runtime;
10. fabricated performance, adoption, service-health, social-proof, or Star claims outside the
    bounded and explicitly labelled synthetic Landing UI demonstration;
11. Pages deployment before the public-launch gate passes.

## 4. Authorship and Evidence Contract

### 4.1 Role boundary

Approved public copy may summarize the original baseline as built 100% by AI agents only when the
same page states or links to this boundary:

| Role | Responsibility |
| --- | --- |
| Human | Product intent, requirements discussion, product use, usage feedback, result acceptance |
| AI agents | Product and process design; governance and quality gates; PRD/SDD/ADR/Slice; architecture and contracts; implementation and tests; verification repair; deployment and release assets |

The copy must not imply there was no human participation.

### 4.2 Baseline scope

One reviewed semantic tag selected immediately before public launch identifies the original
AI-authored public baseline. The strong claim applies to that tag and the reviewed baseline record. Later community contributions may be human- or AI-authored.

### 4.3 Evidence map

The marketing site and README must link claims to the smallest useful evidence source:

- product intent -> PRD;
- engineering scope -> Scope Gate;
- architecture decisions -> ADR index;
- incremental delivery -> Slice indexes;
- API truth -> generated contracts;
- verification -> testing strategy and executable gate;
- distribution -> release workflow, manifests, checksums, and installable Release.

Codex conversation publication is optional and cannot block launch.

## 5. Public Site Architecture

### 5.1 Repository and URLs

The exact initial targets are:

```text
Repository:  https://github.com/latentrun/SurgePilot
Site:        https://latentrun.github.io/SurgePilot/
Docs:        https://latentrun.github.io/SurgePilot/docs/
Chinese:     https://latentrun.github.io/SurgePilot/docs/zh-CN/
Japanese:    https://latentrun.github.io/SurgePilot/docs/ja/
Releases:    https://github.com/latentrun/SurgePilot/releases
```

All build assets and internal links must resolve under `/SurgePilot/`. The origin and base use one
configuration source and must not be repeated as unrelated literals through the theme.

### 5.2 VitePress ownership

`docs/site` remains the exact workspace package. It owns:

- one custom static marketing layout at the project root;
- user documentation below `docs/`;
- locale configuration and navigation;
- canonical, alternate, Open Graph, Twitter, JSON-LD, sitemap, and robots output;
- public marketing, demo, and social assets;
- a Pages-compatible not-found route.

The marketing layout must use the approved product Landing as its visual source of truth,
preserving the dark dot-grid composition, typography, glass surfaces, responsive section rhythm,
and signature CSS/SVG motion through VitePress theme components and scoped CSS. It must emit
meaningful static HTML, remain a separate implementation, and must not mount or import the React
product application.

### 5.3 Documentation routes

The user guide retains exactly six semantic pages in each language:

```text
Home, Quickstart, Startup Modes, Configuration, First Run, FAQ
```

English remains authoritative. `zh-CN` and `ja` remain exact mirrors. Existing relative-link and
Configuration template-key tests must be updated to the new source paths rather than removed.

No SDD, PRD, contributor architecture, API reference, AI Skill reference, blog, or seventh user
page enters the user-doc navigation through this Slice.

## 6. Marketing Page Contract

### 6.1 Message hierarchy

The marketing homepage explains, in order:

1. the AI-built original-baseline hook;
2. the AI construction process overview (`How it was built.`);
3. the exact authorship role boundary and Loop Engineering evidence;
4. why SurgePilot is a meaningful real distributed-system proof;
5. the repository evidence chain through repository/README targets rather than replacing the
   original Recent Test Runs panel;
6. concise product architecture and capabilities;
7. the demonstration and installation path;
8. the final GitHub Star action.

The primary CTA is **Star on GitHub**. Secondary actions are **Inspect the Evidence**,
**Watch the Demo**, **Read the Docs**, and **View Releases**. There is no Pages Log in or Sign up
action.

### 6.2 Truthful proof

The original auto-incrementing dashboard throughput/VU values, eight Recent Test Runs rows, and
animated Distributed load mesh node/status/CPU/RAM/VU values are preserved on both Landing variants
as synthetic UI demonstration data. Each affected panel must
carry adjacent wording equivalent to **UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT
BENCHMARK DATA**. These values must not appear in SEO metadata, schema, social copy, README evidence,
launch posts, or any statement of measured capability, adoption, production proof, service health,
or live topology. Repository evidence remains available through the evidence CTA, README, governance links,
and release artifacts; it does not replace the original Recent Test Runs panel.

Only links with real authorized targets are interactive. The self-hosted Landing activates the
exact public Docs and repository targets established by ADR-0026 while retaining Log in and Sign up.
Nonexistent Discord, hosted status, Updates, pricing, or SaaS entries are omitted. `All systems
operational` remains forbidden. The preserved `ANALYTICS_DASHBOARD_LIVE` and `LIVE_UPDATE` UI labels
describe the animation only and are valid solely beside the required example/non-live/non-benchmark
disclaimer on both Landing variants.

### 6.3 Visual boundary

Pages may reuse the SurgePilot Logo and approved visual tokens. Landing-specific CSS remains
scoped. The public site must not import authentication, Query, API client, product Router, or other
product runtime modules.

## 7. Self-hosted Web Indexing Contract

Every product Web response defaults to a crawler-observable `noindex` policy before React route
rendering or auth-session restoration. The policy covers the Marketing Landing, `/login`,
`/register`, authenticated product routes, and fallback routes.

This Slice does not change which product page renders, whether local registration is enabled, or
how authentication redirects work. In addition to preventing self-hosted instances from competing
with the official Pages site, it authorizes only the exact product-Landing Docs/repository links and
truthful presentation-label corrections defined above.

The chosen implementation must have focused tests for the built HTML or serving layer. A
`robots.txt` rule must not prevent crawlers from reading the `noindex` directive.

## 8. SEO and Localization Contract

### 8.1 Required metadata

Every indexable Pages route must have:

- unique title and description;
- self-referencing canonical URL;
- Open Graph title, description, URL, image, and type;
- Twitter Card metadata;
- exactly one visible primary heading;
- language declaration and descriptive image alternatives;
- a stable lowercase URL under the configured project base.

### 8.2 International alternates

Every English/`zh-CN`/`ja` page cluster declares reciprocal alternates for all three variants and
`x-default`. Each locale self-canonicalizes; no localized page canonicalizes to English. Locale
selection remains explicit and never redirects from browser or IP signals.

### 8.3 Crawl and schema output

The build produces one sitemap containing only canonical, indexable Pages routes and one
Pages-compatible `robots.txt` referencing it. Preview URLs, not-found pages, VitePress internals,
and self-hosted application routes stay out of the sitemap.

Structured data is limited to supportable `WebSite`, `SoftwareApplication`, `TechArticle`,
`BreadcrumbList`, and visible FAQ content as applicable. Browser-rendered validation is required;
rich-result eligibility is not promised.

### 8.4 Performance and accessibility

The implementation defines asset budgets before publication and targets field Core Web Vitals of
LCP below 2.5 seconds, INP below 200 milliseconds, and CLS below 0.1 at the 75th percentile.

The existing large documentation hero asset must be optimized. Required fonts use web-appropriate
formats and only necessary weights. Images preserve dimensions/aspect ratio. The marketing Landing
is desktop-Web-first and keeps full signature motion without a Landing-scoped reduced-motion
override by explicit repository-owner decision.

## 9. Private and Public Phase Boundary

### 9.1 Allowed while private

Private implementation may:

- build and preview the complete VitePress site locally;
- run build-only CI without Pages deployment permissions;
- prepare the exact future canonical metadata and route assertions;
- update README and authorship evidence using clearly future-gated public links;
- prepare video/GIF/social assets and launch drafts;
- review privacy, secrets, author metadata, private endpoints, and asset licenses;
- prepare a least-privilege Pages workflow that remains inactive until its separately reviewed
  activation point.

### 9.2 Public launch gate

Public deployment requires all of the following on the exact launch candidate:

1. approved privacy/license review and any rewrite completed;
2. repository migrated to `latentrun/SurgePilot`;
3. complete repository verification green;
4. semantic original-baseline tag selected and verified;
5. tagged Release, images, Runtime assets, checksums, installer, and bundle anonymously usable;
6. Pages artifact, docs, metadata, alternates, sitemap, and outbound links verified;
7. demo and social assets reviewed for secrets and claim accuracy.

Only after these gates pass may repository visibility, Release, Pages, and external launch posts be
coordinated. Public launch does not change release commands or readiness semantics.

## 10. Implementation Sequence

At the repository owner's explicit review decision, P2-07 private-stage implementation follows
separately reviewable changes and checkpoints inside the launch preparation review so the complete preparation can be
accepted or reverted atomically:

1. governance activation;
2. VitePress route restructure and base validation;
3. static marketing homepage;
4. technical SEO, international alternates, and asset budgets;
5. self-hosted `noindex` isolation;
6. README, repository metadata, and authorship evidence;
7. demo and launch materials;
8. public-readiness and provenance review;
9. coordinated public activation after all private gates pass; this remains outside the private
   implementation PR.

No checkpoint may bypass an earlier dependency or combine unrelated product behavior. Public
visibility, organization migration, baseline tagging, Release publication, and Pages deployment
activation still require the final launch approval and are not performed by the launch preparation review.

## 11. Acceptance Criteria

### 11.1 Private implementation

1. VitePress emits meaningful static HTML for marketing and all eighteen documentation pages.
2. Every route and asset resolves under `/SurgePilot/` without host-root assumptions.
3. Locale page-set, relative-link, and Configuration key-drift checks remain green.
4. Every indexable route has unique metadata, self-canonical, reciprocal alternates, and correct
   social preview data.
5. Sitemap, robots, JSON-LD, 404, keyboard/accessibility, full-motion, and asset-budget checks pass.
6. Product Web exposes `noindex` before client routing while login, registration, auth, and
   protected-route behavior remain unchanged.
7. Every authorship, architecture, verification, and release claim maps to repository evidence.
8. Private CI cannot deploy Pages accidentally.

### 11.2 Public launch

1. Anonymous users can access the repository, Pages, all localized docs, images, Release assets,
   checksums, and installer.
2. The original-baseline tag points to the exact reviewed baseline.
3. Live canonical, sitemap, hreflang, social preview, schema, and 404 output match the approved URL
   model.
4. GitHub About, topics, website URL, License, Security policy, and social preview are correct.
5. External posts use the approved authorship boundary and contain no unsupported benchmark,
   adoption, or production-proven claim.

## 12. Verification Strategy

Later implementation plans must use test-first changes where behavior is executable. The minimum
verification set includes:

- focused route/base/locale/link/configuration contract tests;
- VitePress production build inspection;
- rendered metadata and JSON-LD browser checks;
- keyboard/accessibility and full-motion parity checks;
- asset-size budget checks;
- Web build or response inspection for `noindex`;
- existing Web auth/landing tests;
- repository link and public-readiness scans;
- full `make verify` before public candidate approval;
- clean anonymous release and Pages smoke on the launch candidate.

## 13. Remaining Risks

1. A repository correction can change source identifiers and requires every evidence link to be regenerated.
2. GitHub Pages project-base errors can break all assets even when local root preview passes.
3. GitHub Pages custom headers are limited, so the self-hosted `noindex` and Pages crawl policy must
   not assume unavailable header configuration.
4. The absolute AI-authorship claim can damage credibility if later copy omits the role boundary or
   baseline scope.
5. Marketing/product visual duplication can drift; release review aligns approved brand assets and
   claims without coupling their runtimes.
6. GitHub and community launch rules can change; distribution copy and timing require a final
   launch-day review.
