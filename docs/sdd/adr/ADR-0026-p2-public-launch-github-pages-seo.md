# ADR-0026: P2 Public Launch, GitHub Pages, and SEO

- Status: Accepted
- Scope: P2-07 public repository launch, unified GitHub Pages site, SEO, and indexing boundary
- Active Slice: `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`
- Target repository: `latentrun/SurgePilot`
- Initial public origin: `https://latentrun.github.io/SurgePilot/`

## Context

SurgePilot is currently developed in a private repository. Its public launch is intended to make
the repository, a static marketing site, the localized user documentation, and an installable
tagged Release available together. The primary public objective is legitimate GitHub Star growth
and project awareness rather than hosted-service registration or commercial adoption.

The current product Web application already has an unauthenticated Marketing Landing authorized by
ADR-0013, but that route belongs to each self-hosted product instance, requires the React product
runtime, and retains product Log in and Sign up actions. The existing `docs/site` VitePress package
provides a bounded private-stage user guide localized through ADR-0025, but ADR-0025 explicitly
forbids GitHub Pages, a public URL, a project-path `base`, README online links, and route changes.

The approved public narrative treats SurgePilot as evidence that AI agents can build a real
distributed system. That statement needs an exact human/AI responsibility boundary and an
immutable launch baseline. It must be supported by repository artifacts rather than fabricated
performance, adoption, status, or Star claims.

A new governance decision is therefore required before publication work can begin. It must keep
the public marketing site separate from self-hosted product routing, preserve existing product and
release contracts, and define the exact point at which private preparation may become public
deployment.

## Options Considered

### Option A: One VitePress build for marketing and documentation

Accepted. Extend the existing `docs/site` package so one statically generated GitHub Pages artifact
owns the marketing homepage at the project root and the user guide below `/docs/`.

This keeps one origin, one build, one project `base`, one navigation system, and one metadata and
internationalization source. It produces meaningful static HTML without adding another framework.

### Option B: React marketing application plus VitePress documentation

Rejected. A separate React build would simplify some visual reuse from the product Landing, but it
would require two public builds, artifact merging, duplicate metadata configuration, and a separate
pre-rendering solution to avoid a client-only marketing shell.

### Option C: Hand-maintained static HTML marketing page plus VitePress documentation

Rejected. Plain static HTML would be fast, but it would duplicate public navigation, metadata,
assets, and URL handling without providing a useful boundary for the small initial site.

## Decision

### 1. Public repository and canonical site

The target public repository is:

```text
https://github.com/latentrun/SurgePilot
```

The initial canonical GitHub Pages URLs are:

```text
https://latentrun.github.io/SurgePilot/
https://latentrun.github.io/SurgePilot/docs/
https://latentrun.github.io/SurgePilot/docs/zh-CN/
https://latentrun.github.io/SurgePilot/docs/ja/
```

The initial launch has no custom domain. The production origin and `/SurgePilot/` project base must
have one configuration source so a later domain migration does not require scattered edits.

### 2. One VitePress public site

`docs/site` remains one pnpm workspace package and becomes the only GitHub Pages build. It owns:

1. one English-first static marketing homepage at the Pages project root;
2. the six authoritative English user-documentation pages below `/docs/`;
3. exact Simplified Chinese and Japanese mirrors below `/docs/zh-CN/` and `/docs/ja/`;
4. shared public navigation, metadata, sitemap, robots, social assets, and structured data.

The existing exact six-page locale mirror and Configuration template-drift contracts remain. The
route prefix changes from the private-stage root layout to `/docs/` only through P2-07. There is no
browser-language or IP-based redirect.

### 3. Separate marketing and self-hosted product surfaces

The Pages homepage uses the existing product Marketing Landing as its visual source of truth but
remains a separate static implementation. It preserves the product Landing's dark dot-grid
composition, typography, glass surfaces, responsive section rhythm, and signature CSS/SVG motion.
It has no product authentication dependency and no Log in, Sign up, hosted-service, or pricing
promise. Its primary action is Star on GitHub, followed by evidence, documentation, and Release
links.

The `apps/web` Marketing Landing remains the entry to a particular self-hosted SurgePilot instance
and keeps its existing product authentication actions. P2-07 additionally authorizes that Landing
to activate only the exact public Docs and repository links established by this ADR. Both Landing
variants preserve the original animated synthetic dashboard values, Recent Test Runs, and
Distributed load mesh as visual UI demonstration data. Those surfaces require an adjacent explicit
example/non-live/non-benchmark label and must never be presented as measured performance, adoption,
service health or topology, production
proof, structured data, or repository evidence. It does not add a hosted status service, runtime
health integration, or any other product capability. Pages and product Web intentionally keep
separate framework code; P2-07 does not create a cross-application component library.

All self-hosted Web routes default to a crawler-observable `noindex` policy, including `/`,
`/login`, `/register`, and authenticated routes. The official Pages origin is the only indexable
marketing surface. `robots.txt` must not hide those routes from the directive that establishes
`noindex`.

### 4. AI-authorship claim

Public copy may use the strong hook that the original public baseline was built 100% by AI agents
only when it includes or links to this exact responsibility boundary:

- **Human:** product intent, requirements discussion, product use, usage feedback, and result
  acceptance.
- **AI agents:** product and engineering-process design; PRD, SDD, ADR, and Slice authorship;
  architecture, contracts, implementation, tests, quality-gate design and enforcement,
  verification-failure resolution, deployment, and release assets.

One reviewed semantic-version tag, selected during public-readiness review, identifies the original
AI-authored public baseline. The claim applies to that baseline and its preserved baseline record.
Future community contributions may be human- or AI-authored and require no model or prompt
attestation.

Private development records are not a launch dependency. Repository governance materials,
contracts, verification gates, and release artifacts form the primary evidence chain.

### 5. SEO and internationalization

Every indexable Pages route requires a unique title and description, self-canonical URL, Open
Graph and Twitter metadata, one primary heading, stable language metadata, and descriptive image
alternatives. The public build must produce a canonical-only sitemap and a Pages-compatible
`robots.txt`.

English, `zh-CN`, and `ja` documentation equivalents must declare reciprocal language alternates
plus `x-default`, and every locale page must self-canonicalize. Structured data is limited to facts
visible and supportable from the page and repository. Rendered schema must be validated with a
JavaScript-capable browser; static text fetching alone is insufficient evidence.

Public assets must have explicit performance budgets. By repository-owner review decision, the
marketing Landing is desktop-Web-first and preserves the product Landing's full signature motion,
including counters, CSS/SVG loops, and reveal effects, without a Landing-scoped
`prefers-reduced-motion` override. Large hero images and fonts must still be optimized before
publication.

### 6. Private preparation and public activation

While the repository is private, implementation may prepare and test the complete static artifact,
metadata, public-readiness checks, README copy, authorship evidence, demo assets, and launch
runbook. Private CI may build and validate the site.

At the repository owner's explicit review decision, those private-stage changes may be delivered
as sequential, independently verified changes in the launch preparation review so the entire
preparation has one atomic review/revert boundary. This delivery choice does not waive any
acceptance gate and does not authorize public activation from that review.

Pages deployment permissions and public deployment remain inactive until the dedicated launch
gate confirms:

1. privacy and asset-license review;
2. target organization/repository migration;
3. exact candidate verification;
4. immutable baseline tag and installable Release readiness;
5. anonymous repository, image, bundle, installer, Pages, and documentation access.

The public repository, Pages site, localized docs, and tagged Release launch together. P2-07
consumes the existing P2-05/P2-06 release artifacts and commands; it does not modify their runtime,
installer, Compose, or publication integrity contracts.

### 7. Legitimate Star-growth boundary

The launch optimizes for repository discovery and legitimate Star conversion through accurate
technical storytelling, auditable evidence, public documentation, demo assets, GitHub metadata,
and community distribution. Purchased Stars, fake accounts, misleading giveaways, fabricated
adoption, synthetic benchmarks represented as real, and other artificial growth methods are
forbidden.

## Consequences

1. The user-documentation routes move below `/docs/` when P2-07 implementation activates them.
2. Marketing and user documentation share one Pages origin and static build.
3. The product Web and public marketing homepage intentionally maintain separate code suited to
   their different routing and conversion responsibilities.
4. Public-site changes require metadata, locale, project-base, static-output, accessibility, and
   performance regression coverage.
5. The original AI-authored claim remains accurate after ordinary community contributions because
   it is bound to an immutable baseline.
6. The repository needs a security and privacy review, and possibly a reviewed repository correction,
   before public visibility.
7. A later custom-domain decision requires a new canonical and redirect migration review.

## Non-goals

P2-07 does not authorize:

1. a hosted SurgePilot SaaS, hosted signup, pricing, billing, lead capture, or newsletter;
2. a blog, CMS, programmatic SEO, automatic content generation, or multi-version documentation;
3. a custom domain at initial launch;
4. automatic translation, language redirection, or product UI/API-message localization;
5. publication of private development records;
6. mandatory AI provenance for future community contributions;
7. a new UI component system or cross-app marketing component package;
8. fabricated benchmark, adoption, service-status, GitHub Star, or other social-proof claims; the
   explicitly labelled synthetic Landing dashboard, Recent Test Runs, and Distributed load mesh UI
   demonstrations are not evidence and are the only bounded presentation-data exception;
9. changes to the API, database, contracts, Runner protocol, Run state machine, storage,
   Workspace/RBAC, Runtime, release installer, Compose topology, or Load Node behavior;
10. public deployment before the P2-07 launch acceptance gate passes.

## Related ADRs

- ADR-0013 remains authoritative for the self-hosted product Marketing Landing, Logo, route, and
  authentication behavior. ADR-0026 narrowly supersedes its disabled-link restriction for the exact
  public Docs and repository targets and authorizes the explicitly labelled synthetic UI
  demonstration described above; it does not add API calls or other product behavior.
- ADR-0025 remains authoritative for the exact English/`zh-CN`/`ja` six-page mirror and localization
  rules. ADR-0026 partially supersedes only its root-route preservation and its GitHub Pages,
  public URL, project-base, and online-link exclusions.
- ADR-0017, ADR-0018, ADR-0020, ADR-0021, and ADR-0024 remain authoritative for application
  distribution, Runtime assets, release startup, configuration confirmation, and installation.

## References

- `docs/sdd/public-launch-github-pages-and-star-growth-plan.md`
- `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`
- `docs/sdd/adr/ADR-0025-public-user-documentation-localization.md`
- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/site`
- `apps/web/src/features/marketing`
