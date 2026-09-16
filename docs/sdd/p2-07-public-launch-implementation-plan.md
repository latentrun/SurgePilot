# P2-07 Public Launch Implementation Plan

**Goal:** Prepare the complete private-stage `latentrun/SurgePilot` public launch: one static VitePress marketing/docs site, crawlable SEO output, self-hosted Web indexing isolation, repository/authorship evidence, launch assets, and public-readiness gates.

## Global constraints

- `docs/site` remains the only public-site package.
- The public origin is `https://latentrun.github.io/SurgePilot/` with project base `/SurgePilot/`.
- English documentation is authoritative with exact `zh-CN` and `ja` six-page mirrors.
- The primary conversion action is legitimate **Star on GitHub**.
- Human responsibility is product intent, requirements discussion, product use, feedback, and acceptance.
- AI-agent responsibility is product/process design, governance, architecture, contracts, implementation, tests, verification repair, deployment, and release assets.
- No hosted service, pricing, signup, fabricated benchmark/adoption/status/Star claim, automatic translation, custom domain, blog/CMS, or programmatic SEO promise.
- Private validation may build the Pages artifact but may not activate public visibility or deployment.

## Work packages

### 1. Governance and site foundation

Align the P2-07 governance documents with one VitePress site, the public repository identity, the approved owner decisions, and the launch gates. Preserve manual public activation and the existing release/runtime contracts.

### 2. Routes and shared configuration

Move the six English user pages and their exact locale mirrors below `docs/`. Establish one typed source for origin, base, repository links, route helpers, metadata, and locale navigation. Verify the project base, internal links, one heading per page, and absence of host-root asset assumptions.

### 3. Static marketing homepage

Implement a meaningful SSR marketing document with the AI-baseline hook, human/AI boundary, evidence links, distributed-system proof, and Star/Docs/Releases calls to action. Use scoped VitePress theme code, accessible focus states, responsive layout, approved full-motion desktop presentation, and explicit adjacent labels for synthetic UI demonstrations. Do not import the React product runtime.

### 4. SEO, localization, and budgets

Produce unique metadata, self-canonical URLs, Open Graph and Twitter cards, reciprocal locale alternates, `x-default`, supportable JSON-LD, a canonical-only sitemap, and project-scoped robots output. Validate rendered output, image alternatives, asset budgets, and 404 `noindex` behavior.

### 5. Self-hosted indexing isolation

Apply crawler-observable `noindex` to self-hosted Web routes before route rendering or session restoration. Keep robots behavior compatible with observing the directive, and test the serving layer without changing product routing or authentication behavior.

### 6. Readiness and launch material

Prepare repository metadata, authorship wording, security and license checks, demo guidance, community drafts, and the runbook. Every item must refer only to the reviewed launch candidate and the approved launch steps. Do not publish unsupported metrics or links that have not passed anonymous checks.

## Acceptance gates

- six-page English/`zh-CN`/`ja` page sets and relative links are exact;
- the public site uses one origin/base configuration;
- marketing output is static, meaningful, accessible, and free of product-authentication promises;
- synthetic dashboard values have adjacent non-live/non-benchmark labels;
- SEO, locale, schema, sitemap, robots, and self-hosted `noindex` checks pass;
- repository, package, asset, credential, privacy, and license review is approved;
- the installable release and both Runtime architectures are ready;
- anonymous repository, image, bundle, installer, Pages, and documentation checks pass;
- owner approval is recorded before public visibility, release publication, metadata changes, or Pages deployment.

## Out of scope

No API, route, table, migration, Runner protocol, database schema, release execution contract, hosted service, SDK, MCP server, product localization, or automatic translation is added by this plan.
