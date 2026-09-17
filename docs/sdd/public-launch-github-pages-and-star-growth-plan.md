# Public Launch, GitHub Pages, SEO, and Star-Growth Plan

- Status: Proposed for review; this document does not activate implementation
- Target repository: `latentrun/SurgePilot`
- Planned public site: `https://latentrun.github.io/SurgePilot/`
- Planned documentation root: `https://latentrun.github.io/SurgePilot/docs/`
- Primary outcome: maximize legitimate GitHub Star growth and increase SurgePilot and LatentRun
  project awareness
- Public launch shape: repository, GitHub Pages site, multilingual documentation, and an
  installable tagged Release launch together

## 1. Purpose

This plan records the approved product-marketing direction and separates work that should be
prepared while the repository is private from actions that must wait until the repository is
public. It is the review source for later governance, design, implementation, release-readiness,
and launch implementation.

This document is intentionally non-authorizing. The current scope gate, ADR-0013, ADR-0025, and
repository workflow still prohibit GitHub Pages publication, a public documentation URL,
project-path VitePress `base`, online-documentation links, and broader marketing-site behavior.
Implementation must begin with a separately accepted governance change that explicitly activates
the bounded work described here.

## 2. Strategic Decision

SurgePilot is not primarily marketed as another load-testing product. Its primary public story is:

> **A real distributed system built 100% by AI agents.**

The working self-hosted distributed load-testing platform is the proof that the project is not a
prompt-generated frontend demonstration. Its independent Linux Runners, multi-node execution,
state-machine safety, security boundaries, API contracts, tests, release packaging, and
verification gates establish the complexity and credibility of the AI-engineering claim.

The positioning has three layers:

1. **Attention:** the original public baseline was built entirely by AI agents.
2. **Proof:** the result is a real, inspectable, runnable distributed system.
3. **Reason to Star:** the repository makes its engineering lifecycle auditable and useful to
   people studying agentic software engineering.

Product adoption, registrations, and commercial leads are not launch success criteria. They must
not displace the GitHub discovery and Star-conversion objective.

## 3. Authorship Boundary

### 3.1 Accurate public statement

The public claim must define the roles precisely:

> **Human role:** define product intent, discuss requirements, use the product, provide feedback,
> and decide whether the result is acceptable.
>
> **AI-agent role:** design the product and engineering process; author the PRD, SDDs, ADRs,
> Slices, architecture, contracts, implementation, and tests; define and enforce quality gates;
> resolve verification failures; and produce deployment and release assets.

The project must not claim that no human participated. Human intent, conversation, usage feedback,
and acceptance remain part of the process. The differentiator is that the human did not manually
produce the original baseline's first-party engineering artifacts.

### 3.2 Evidence level

The initial public evidence model uses repository-verifiable facts rather than private development
records. Additional supporting material may be added later, but it is optional and is not a launch
dependency.

The evidence hierarchy is:

1. repository provenance preserved after a public-readiness review;
2. PRD -> SDD -> ADR -> Slice -> contract -> implementation -> test -> release traceability;
3. executable verification gates and current verification results;
4. architecture and deployment artifacts;
5. an explicit authorship methodology and human/AI responsibility statement;
6. optional later supporting material with English context and privacy review.

### 3.3 Immutable launch baseline

Before publication, one reviewed semantic-version Git tag must identify the **original AI-authored
public baseline**. The exact version is chosen only after release-readiness review; this plan does
not preselect `v1.0.0` or imply production adoption.

The strong authorship claim applies to that baseline and its preserved baseline record. After
publication, SurgePilot accepts ordinary human- or AI-authored community contributions without
requiring model, prompt, or provenance attestations. Later copy must not imply that every future
community contribution is AI-authored.

Recommended post-launch wording:

> The original public baseline was authored end-to-end by AI agents under human direction.
> SurgePilot is now open to community contributions.

## 4. Public URL and Site Architecture

### 4.1 Canonical URL model

The initial launch uses GitHub Pages without a custom domain:

```text
Marketing home        https://latentrun.github.io/SurgePilot/
English docs          https://latentrun.github.io/SurgePilot/docs/
Chinese docs          https://latentrun.github.io/SurgePilot/docs/zh-CN/
Japanese docs         https://latentrun.github.io/SurgePilot/docs/ja/
GitHub repository     https://github.com/latentrun/SurgePilot
GitHub Releases       https://github.com/latentrun/SurgePilot/releases
```

All public-site absolute URLs, canonical URLs, sitemap entries, Open Graph URLs, and JSON-LD URLs
must use this model. The production origin and project base must have one configuration source so a
future custom-domain migration does not require scattered replacements.

### 4.2 One VitePress public site

The existing `docs/site` VitePress package becomes the single public-site build. It owns both the
marketing homepage and the user documentation:

```text
docs/site/
  index.md or a custom marketing layout      -> /SurgePilot/
  docs/index.md                              -> /SurgePilot/docs/
  docs/quickstart.md                         -> /SurgePilot/docs/quickstart
  docs/startup-modes.md                      -> /SurgePilot/docs/startup-modes
  docs/configuration.md                      -> /SurgePilot/docs/configuration
  docs/first-run.md                          -> /SurgePilot/docs/first-run
  docs/faq.md                                -> /SurgePilot/docs/faq
  docs/zh-CN/...                             -> /SurgePilot/docs/zh-CN/...
  docs/ja/...                                -> /SurgePilot/docs/ja/...
  .vitepress/                                shared build, theme, metadata, and navigation
```

The marketing homepage is statically generated through VitePress. It may use a custom VitePress
layout and scoped CSS, but it must not become a client-only React shell.

### 4.3 Marketing site and product Web remain separate

The Pages marketing homepage is based visually on the current `apps/web` Marketing Landing but is
a separate implementation with a different job:

| Surface | Purpose | Primary actions | Indexing |
| --- | --- | --- | --- |
| GitHub Pages homepage | project discovery and Star conversion | Star, Evidence, Demo, Docs, Releases | indexable |
| Self-hosted Web homepage | instance entry | Log in, Sign up, enter product | `noindex` |

The two surfaces may share brand assets, color definitions, typography choices, and approved copy
principles. They must not introduce a cross-app UI package merely to avoid duplication. Their
authentication, release, routing, and indexing boundaries are intentionally different.

### 4.4 Self-hosted indexing policy

Every self-hosted product Web surface defaults to `noindex`, including `/`, `/login`, `/register`,
and authenticated routes. The official GitHub Pages site is the only indexable marketing source.
The implementation design must choose a response/header or document-level mechanism that applies
before route rendering and is covered by automated tests. `robots.txt` must not be used in a way
that prevents crawlers from observing the `noindex` directive.

## 5. Marketing Homepage Information Architecture

### 5.1 Conversion path

The intended visitor path is:

```text
External post, search result, or shared link
  -> understand the AI-built claim
  -> see that the repository contains a real distributed system
  -> inspect evidence
  -> visit GitHub
  -> Star
```

### 5.2 Hero

Recommended message direction:

```text
Can AI agents build a real distributed system?
SurgePilot is the proof.
```

The supporting copy must state that the original baseline's first-party artifacts—from product
requirements and architecture decisions through code, tests, quality gates, and release
infrastructure—were authored by AI agents under human direction. It must immediately identify the
result as a working self-hosted distributed load-testing platform.

CTA priority:

1. **Star on GitHub**
2. **Inspect the Evidence**
3. **Watch the Demo**
4. **Read the Docs**
5. **View Releases**

The Pages homepage has no Log in, Sign up, or hosted-service registration promise.

### 5.3 Proof before product detail

The first content after the hero should answer four questions:

1. What does "100% AI-built" mean?
2. What did the human do?
3. Why is this not a toy application?
4. Where can a skeptical visitor verify the claim?

The proof section should link to real repository artifacts rather than rely on unsupported
statistics. Appropriate evidence includes the PRD, SDD scope gate, ADR index, Slice index,
contracts, test strategy, release workflow, and exact verification command.

### 5.4 Real-system complexity

The product section should demonstrate why SurgePilot is a meaningful test of AI engineering:

- decoupled Web, API, api-worker, and independent Runner;
- remote Linux Load Nodes and multi-node orchestration;
- PostgreSQL, MinIO, InfluxDB, and Grafana boundaries;
- Workspace, permission, secret, and credential safety;
- Run state machine, snapshots, artifacts, and reports;
- public API and governed AI-agent operation;
- multi-architecture application and Runtime release assets;
- contract freshness, test coverage, and end-to-end verification.

The section remains concise and sends deeper product-operation questions to `/docs/`.

### 5.5 Labelled UI demonstration and repository-backed claims

The public homepage preserves the product Landing's animated `842,000 REQ/SEC`, VU counter, sample
Run rows, and Distributed load mesh node/status/CPU/RAM/VU values only as visibly adjacent UI
demonstration/example data that is explicitly not a live service, live topology, or benchmark.
These values are never performance, adoption, status, or repository evidence.

Preferred launch metrics are repository-verifiable and include an exact commit or release context,
for example:

- accepted ADR and Slice counts;
- test and coverage-gate results;
- supported release architectures;
- independently deployable components;
- generated contract freshness;
- tagged baseline version.

No metric is published unless its generation method and source are documented.

### 5.6 Trust and footer

The current disabled Docs, GitHub, Releases, License, and Security text becomes real links only
after the targets exist. Nonexistent Community, Discord, Updates, pricing, hosted signup, or status
services are omitted rather than rendered as disabled promises.

## 6. README and Repository Discovery

### 6.1 Root README responsibility

The English README is the GitHub conversion surface. Its first viewport must communicate:

1. the AI-authored original-baseline claim;
2. the working distributed-system proof;
3. the exact authorship boundary;
4. links to evidence, demo, public site, documentation, and Release.

The full architecture, operation, and contributor detail can remain below. The README should not
be rewritten as a generic SaaS landing page.

Chinese and Japanese README files remain localized discovery aids. English stays authoritative and
is the primary global-launch copy.

### 6.2 GitHub repository metadata

The public-launch checklist must set and verify:

- repository description;
- GitHub Pages website URL;
- topics such as `ai-agents`, `agentic-engineering`, `load-testing`, `performance-testing`,
  `self-hosted`, `distributed-systems`, `jmeter`, and `taurus` after final review;
- repository social preview image;
- MIT License detection;
- Security policy visibility;
- Discussions/Issues choices;
- the public Release and installation path.

No source file can configure all of these settings, so they remain explicit launch-day checklist
items with screenshots or API output retained as review evidence.

## 7. SEO and Internationalization Contract

### 7.1 Page-level metadata

Every indexable page requires:

- one unique, intent-aligned title;
- one unique meta description;
- a self-referencing canonical URL;
- Open Graph title, description, URL, image, and type;
- Twitter Card metadata;
- one visible primary heading;
- descriptive image alternative text;
- a stable, lowercase, hyphenated URL;
- appropriate language declaration.

Recommended homepage title direction:

> SurgePilot: A Distributed System Built 100% by AI Agents

The supporting description must identify the distributed load-testing platform so the AI claim
has concrete technical context.

### 7.2 Sitemap and robots

The public build produces one sitemap containing only canonical, indexable GitHub Pages URLs. A
Pages-compatible `robots.txt` permits public-site crawling and references that sitemap.

Private preview URLs, VitePress internal artifacts, error pages, and self-hosted application routes
must not enter the sitemap.

### 7.3 Localized documentation

English remains authoritative. Simplified Chinese and Japanese keep exact page mirrors. Each page
cluster must declare reciprocal alternates for:

- `en` or the final approved English code;
- `zh-CN`;
- `ja`;
- `x-default` pointing to the English fallback.

Every locale page self-canonicalizes. No non-English page canonicalizes to English. There is no
browser-language or IP-based redirect. Page titles and descriptions are independently localized
rather than inherited as one generic locale description.

### 7.4 Structured data

The project should add only structured data it can substantiate:

- `WebSite` and `SoftwareApplication` on the marketing homepage;
- `TechArticle` where appropriate for documentation;
- `BreadcrumbList` for documentation hierarchy;
- `FAQPage` only for the visible FAQ content, without promising a Google rich result.

Rendered JSON-LD must be checked with a JavaScript-capable browser and Google's Rich Results Test;
static text fetching alone is not accepted as schema validation.

### 7.5 Performance budget

The public site should target field Core Web Vitals of LCP below 2.5 seconds, INP below 200
milliseconds, and CLS below 0.1 at the 75th percentile. Private-stage build checks should enforce
practical asset budgets before field data exists.

The current approximately 2 MB documentation hero PNG must be replaced with responsive modern
formats or otherwise reduced substantially before public launch. Local fonts should use only the
weights required by the Pages site, use web-appropriate formats, and keep `font-display: swap`.
By later repository-owner review decision, the desktop-first marketing Landing preserves full
signature motion without a Landing-scoped `prefers-reduced-motion` override.

## 8. Demo Video and Social Assets

### 8.1 Required launch assets

Prepare, but do not publish while the repository is private:

- a 60-120 second English-captioned demonstration video;
- a short silent GIF or compact video loop for the README;
- a GitHub social preview image;
- an Open Graph image for Pages;
- a static fallback screenshot;
- platform-specific crops where a launch channel requires them.

### 8.2 Video narrative

The recording should show evidence and a real flow rather than only page animation:

1. the repository governance path;
2. the system architecture;
3. one official startup path;
4. Scenario and Test Plan creation or prepared examples;
5. a real distributed Run;
6. the resulting report and Monitoring surface;
7. the GitHub Star CTA.

The recording plan must specify screen size, browser zoom, prepared data, narration/subtitles,
commands, secret redaction, export formats, and a final sensitive-information review. The
private-stage implementation should provide a reproducible recording script and conversion commands so the
repository owner does not need prior video-editing experience.

## 9. Private-Stage Work Plan

Review outcome: the repository owner chose to keep every private-stage checkpoint as sequential
changes in one launch preparation review so dissatisfaction can be handled by reverting one
change. The following checkpoint descriptions therefore describe sequential review checkpoints
inside that preparation. The accepted governance ADR/Slice remains the prerequisite, and public
activation remains outside that preparation.

### Checkpoint 1: Activate bounded public-launch governance

Authorize only:

- one combined VitePress marketing and documentation site;
- the `latentrun/SurgePilot` GitHub Pages project URL;
- `/docs/` English, Chinese, and Japanese routes;
- publication metadata, sitemap, robots, canonical, hreflang, and structured data;
- README online links after their targets exist;
- a build-only private-stage check and a separately gated public Pages deployment;
- the original-baseline authorship statement and evidence map;
- self-hosted Web `noindex` behavior;
- public-launch assets and repository metadata preparation.

It must not activate a blog, CMS, analytics product integration, hosted signup, pricing, community
service, custom domain, automatic translation, multi-version docs, or unrelated product work.

### Checkpoint 2: Restructure and validate the VitePress public site

- Move user documentation below `/docs/` while retaining exact locale mirrors.
- Establish one configurable production origin and `/SurgePilot/` base.
- Add route, locale, relative-link, and project-base regression checks.
- Preserve the Configuration template-drift contract in every locale.
- Add a deterministic static build and local preview path.

### Checkpoint 3: Implement the static marketing homepage

- Rebuild the approved visual direction as a VitePress custom layout.
- Add the Star-first information architecture and real outbound links.
- Add the authorship definition, evidence map, and distributed-system proof.
- Remove unsupported live/adoption/performance implications.
- Preserve the desktop-first product composition and full signature motion.

### Checkpoint 4: Add technical SEO and asset budgets

- Add unique metadata, canonical URLs, hreflang, sitemap, robots, Open Graph, Twitter Cards, JSON-LD,
  and a 404 page.
- Add generated-output assertions for the exact GitHub Pages base.
- Optimize the hero, social images, and public-site fonts.
- Add a browser-rendered schema and metadata verification procedure.

### Checkpoint 5: Isolate self-hosted application indexing

- Add a default `noindex` policy for every self-hosted Web route.
- Test the policy before client routing and authentication restoration.
- Keep existing login, registration, and product routing behavior unchanged.
- Do not link a self-hosted instance to an assumed official hosted service.

### Checkpoint 6: Prepare repository and authorship evidence

- Restructure the README first viewport for the AI claim and evidence path.
- Add the authorship methodology and original-baseline definition.
- Add public-facing License, Security, Contributing, and Code of Conduct decisions as separately
  reviewed files where absent.
- Audit future repository links and confirm the published
  `latentrun/SurgePilot` namespace.
- Prepare GitHub About, topics, social preview, and launch checklist content.

### Checkpoint 7: Prepare demo and launch materials

- Add the English video storyboard and command-by-command recording guide.
- Produce reviewed video/GIF/social-image assets.
- Prepare English-first launch drafts for Hacker News, Reddit, X, and other selected technical
  communities; prepare Chinese follow-up material separately.
- Ensure every claim links back to auditable repository evidence.

### Checkpoint 8: Public-readiness and provenance review

- Scan the complete repository for credentials, private keys, tokens, cookies, `.env` data, private
  links, internal hosts/IPs, personal paths, author email exposure, and unlicensed assets.
- Produce a reviewed correction map for only the unsafe material.
- Correct and re-verify the retained baseline record before organization migration.
- Select the semantic launch version and freeze the original AI-authored baseline candidate.
- Run full repository, release, Pages, link, metadata, and security verification.

Any repository correction must occur before public visibility. Once corrected, all retained source
identifiers and evidence links must reference the corrected record.

## 10. Public Launch-Day Runbook

The launch should be coordinated rather than exposing an incomplete repository in stages.

1. Freeze private writes and record the final pre-migration candidate.
2. Complete the approved repository correction and secret/license review.
3. Push or transfer the reviewed repository to `latentrun/SurgePilot` while preserving the approved
   baseline record.
4. Update and verify repository/release links that cannot be valid before migration.
5. Run the complete verification gate on the exact public candidate.
6. Create the approved semantic launch tag that identifies the original AI-authored baseline.
7. Publish the installable tagged Release and verify anonymous download, checksums, image access,
   and installation instructions.
8. Change repository visibility to Public.
9. Enable the least-privilege GitHub Pages deployment workflow and deploy the exact reviewed site
   artifact.
10. Verify every canonical URL, sitemap entry, alternate, social card, structured-data block,
    GitHub link, Release link, and installation command against the live origin.
11. Configure GitHub About, topics, website URL, social preview, Issues/Discussions, and security
    policy visibility.
12. Publish the English launch materials only after the repository, Pages site, docs, demo, and
    Release all succeed anonymously.
13. Submit the sitemap to Google Search Console and Bing Webmaster Tools after ownership setup.
14. Record launch time, channel URLs, referral tags, and initial measurements for later review.

No `latest` installer, public URL, Page, or social post is announced before an anonymous clean
environment verifies it.

## 11. Post-Launch Star-Growth Work

Traditional SEO supports long-term discovery, but the initial Star launch depends primarily on
credible technical storytelling and community distribution.

### 11.1 English-first launch narrative

The recommended editorial frame is:

> I used AI agents to build an entire distributed system—from product requirements and governance
> to tests and release. Here is what the repository proves, where the agents failed, and how the
> quality gates kept the system coherent.

The narrative should not be a generic product announcement. It should invite technical inspection,
state limitations, and link to reproducible evidence.

### 11.2 Distribution sequence

Prepare channel-specific copy instead of posting identical text everywhere. Candidate channels
include Hacker News (`Show HN`), relevant Reddit communities, X, LinkedIn, Product Hunt, AI-tool
communities, newsletters, and later Chinese technical communities. Channel selection and timing
are reviewed immediately before launch because community rules and audience conditions change.

No purchased Stars, coordinated fake accounts, misleading giveaways, or other artificial Star
schemes are allowed. The objective is maximum legitimate growth.

### 11.3 Measurement

There is no hard Star target. Track:

- GitHub Stars and growth by launch event;
- repository unique visitors and referring sites;
- Pages-to-GitHub outbound click-through rate where measurable without unnecessary tracking;
- Release and demo engagement;
- backlinks and branded search impressions;
- search queries associated with AI agents, agentic engineering, distributed systems, and load
  testing;
- forks, watchers, Issues, and substantive technical discussion as supporting indicators.

Do not optimize for registration, active deployments, or commercial leads unless the project goal
is explicitly changed later.

## 12. Verification and Acceptance Gates

### 12.1 Private implementation acceptance

- Governance explicitly activates every implemented public-site and indexing behavior.
- The VitePress build emits static meaningful HTML for the marketing homepage and all docs pages.
- All expected English, Chinese, and Japanese routes exist below the project base.
- All internal links resolve under `/SurgePilot/` without root-host assumptions.
- Every indexable page has unique metadata and a self-canonical live-target URL.
- Every translated page cluster has reciprocal, valid alternates and `x-default`.
- The sitemap contains only canonical indexable URLs.
- Rendered structured data parses and matches visible content.
- Social previews render using absolute live-target URLs.
- Asset budgets and accessibility checks pass.
- Self-hosted Web responses expose the default `noindex` policy before client routing.
- Existing product authentication, registration, and protected routes remain functional.
- README/authorship claims map to repository evidence and contain no unsupported performance,
  adoption, or production-proven statement.
- Private CI contains no active Pages deployment permission until the activation point approved by
  governance.

### 12.2 Public launch acceptance

- Repository visibility, Pages, docs, tagged Release, anonymous images/downloads, and installer all
  work from a clean unauthenticated environment.
- The launch tag points to the exact reviewed original AI-authored baseline.
- The public record contains no known secrets or private data.
- GitHub About, topics, License, Security, social preview, and website URL are correct.
- Live canonical, redirect, sitemap, hreflang, metadata, 404, and JSON-LD behavior matches the
  approved URL model.
- The demo video and every launch post use accurate role and evidence wording.
- No launch post is published before all preceding checks pass.

## 13. Risks and Controls

| Risk | Impact | Control |
| --- | --- | --- |
| "100% AI-built" is interpreted as no human involvement | credibility loss | publish the exact human/AI boundary next to the claim |
| Later community code invalidates the claim | misleading copy | bind the strong claim to the immutable original public baseline |
| Repository record leaks secrets or private data | security incident | correct reviewed unsafe material before Public visibility |
| Pages project base breaks assets and links | broken launch | generate and test every route against `/SurgePilot/` |
| Marketing and docs compete or fragment authority | weaker discovery | use one VitePress build and one Pages origin |
| Self-hosted instances create duplicate public pages | index dilution | default every product Web surface to `noindex` |
| Synthetic dashboard values appear to be benchmarks | reputation damage | label examples or replace them with repository-backed proof |
| "Production-grade" implies proven adoption | skeptical backlash | describe architecture/gates precisely; do not claim production proof |
| Heavy hero image, fonts, or animation degrade CWV | ranking and UX loss | enforce asset budgets and inspect desktop CWV before launch |
| Private-stage workflow accidentally publishes Pages | premature exposure | keep deployment permissions and public triggers inactive until launch |
| Two copies of the landing drift | inconsistent brand | share brand rules/assets, not runtime code; review copy at release gates |
| GitHub Pages later moves to a custom domain | duplicate indexing | keep one configurable origin and execute a canonical/redirect migration plan |

## 14. Explicit Non-Goals

This plan does not authorize or require:

- a hosted SurgePilot SaaS;
- pricing, billing, signup collection, newsletter capture, or lead scoring;
- a blog, CMS, programmatic SEO pages, or automatic content generation;
- a custom domain at initial launch;
- automatic language redirection or machine-translation publishing;
- multi-version documentation;
- publication of private development records;
- mandatory AI provenance for future community contributions;
- fabricated benchmarks, adoption counts, status data, or GitHub Stars;
- changes to the Runner protocol, Run state machine, API contracts, database, or deployment
  behavior unrelated to public-site readiness;
- implementation merely because this proposed plan is merged.

## 15. Review Decision Requested

Approval of this plan means only that later work may draft the necessary activation ADR/Slice and
implementation plans using these boundaries. It does not itself make GitHub Pages, the public URL,
the route migration, self-hosted `noindex`, or any launch workflow active.

The reviewer should explicitly confirm or revise:

1. the AI-first positioning and authorship boundary;
2. the immutable original public baseline rule;
3. the single VitePress architecture and exact GitHub Pages URL model;
4. the separate indexable marketing and `noindex` self-hosted surfaces;
5. the private/public phase boundary;
6. the coordinated repository + Pages + docs + Release launch;
7. the English-first, legitimate-Star-growth objective;
8. the proposed review sequence and acceptance gates.
