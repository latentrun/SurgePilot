# ADR-0013: P2 Static Marketing Landing and Logo

- Status: Accepted
- Scope: Static public Web landing route, Stitch-derived SurgePilot logo assets, local-only marketing visual assets

## Context

The P2-02 Public API Substrate work creates a programmatic API surface, but it does not by itself authorize a public marketing page. The Web app also needs to migrate the approved Stitch logo and landing visuals without introducing runtime CDN dependencies or pretending that future product areas are available.

The approved visual source is the archived Stitch reference material in `references/logo.svg`, `references/home.html` and `references/manifest.json`. Runtime code must use local assets derived from those references.

## Decision

1. The root Web route `/` may be a public static Marketing Landing page for unauthenticated visitors.
2. Authenticated users visiting `/` must be redirected to `/overview` with `replace` semantics.
3. `/overview` remains the authenticated product home under `AppLayout`.
4. `AppLayout` logo links to `/overview`, not back to the public Landing page.
5. Marketing Landing and Logo are Web-only static presentation work: no API, database, migration, runner, contract, SDK, CMS, MCP, analytics, or external runtime dependency is authorized.
6. The Landing page may link only to existing implemented targets: `/login`, `/register`, and in-page anchors.
7. Register CTA behavior must respect the existing registration route and setup status behavior; if registration is disabled, the registration page remains responsible for showing that state.
8. Docs, API Guide, Community, Security and GitHub items must not be rendered as working links unless a real target is separately provided and authorized. Without a target they must be disabled/non-interactive text.
9. Runtime Web code must not request Tailwind CDN, Google Fonts, Material Symbols, `lh3.googleusercontent.com`, or other remote design assets for this page.
10. The Landing route must be code-split with React Router `lazy` route modules and must not expand the existing centralized page-import pattern in `app/router.tsx`.
11. Landing-specific styling must be scoped under a Marketing Landing root class and must not change product-wide Tailwind tokens or introduce a new UI component system.
12. `SurgePilotLogo` keeps its `decorative` and `className` API and adds explicit variants for full logo and app-icon usage.

## Out of Scope

1. Product Help page, Docs site, API Guide, Community, Security page, GitHub project management, blog, changelog, pricing, CMS, SEO management, analytics, cookie banner, or newsletter capture.
2. Any Public API, PAT, OpenAPI, contract, database, migration, runner or Load Node changes.
3. Any new component library or external runtime UI dependency.
4. Any new P2 capability beyond a static public Web landing and logo migration.

## Consequences

1. `/` is no longer an unauthenticated redirect to `/login`; unauthenticated visitors see the static Landing page.
2. Existing product routes, authenticated shell behavior, login, register and `/overview` remain stable.
3. Future marketing links require a separate accepted governance item or a concrete implemented target.
4. Visual verification must include screenshots against the archived Stitch references and a network check that no remote design assets are requested at runtime.

## References

- `references/logo.svg`
- `references/home.html`
- `references/manifest.json`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `apps/web/AGENTS.md`

## Verification Backfill

The reconstructed ADR-0013 verification is recorded in
`docs/sdd/slices/P2-07-public-launch-github-pages-seo.md` §14. The self-hosted Landing route,
Logo, and authentication behavior are covered by the Web feature tests in
`apps/web/src/features/marketing/` and `apps/web/src/components/surgepilot-logo.test.tsx`, and
the pre-routing crawler isolation that keeps every self-hosted Web route out of search results is
covered by `tests/contract/test_p2_07_public_launch.py`, which checks the `apps/web`
`robots`/`googlebot` directives and the Nginx `X-Robots-Tag` header. The public marketing homepage
remains a separate static VitePress surface, and its visual-parity and synthetic-demonstration
label checks live in `docs/site/tests/verify-built-site.mjs`, so no product API, database,
migration, runner, contract, or external runtime design asset is introduced.
