# ADR-0025: Public User Documentation Localization

- Status: Accepted
- Scope: Private-stage Public User Documentation localization only
- Active surface: `docs/site`
- Related scope: Public User Documentation MVP in `docs/sdd/00-product-scope-and-priority.md`
- Publication amendment: `ADR-0026` partially supersedes only the root-route preservation and the
  GitHub Pages, public URL, project-base, and online-link exclusions. The exact locale mirrors and
  explicit locale selection remain authoritative.

## Context

The private-stage VitePress user documentation currently contains six English pages: Home,
Quickstart, Startup Modes, Configuration, First Run, and FAQ. The root README now serves English,
Simplified Chinese, and Japanese readers, but the deeper user documentation remains English-only.

Localization must preserve the existing English URLs and the bounded six-page navigation. It must
also keep operational commands, product UI labels, environment-variable names, default values,
and source/release configuration coverage synchronized. This expansion does not require or justify
documentation publication, browser-language detection, a new documentation section, or a
multi-version system.

## Options Considered

### Option A: Keep English at root and add locale subdirectories

Accepted. English retains its current routes. Simplified Chinese uses `/zh-CN/` and Japanese uses
`/ja/`, with VitePress native locale navigation and mirrored filenames.

### Option B: Move every language below a locale prefix

Rejected. Moving English to `/en/` would break the current root routes and require redirect or
publication infrastructure that is not active.

### Option C: Build one independent site per language

Rejected. Separate configurations and builds would duplicate navigation, assets, and verification
without adding useful isolation for six mirrored pages.

## Decision

1. English remains authoritative. In the private-stage layout it stays at the VitePress root;
   P2-07/ADR-0026 moves the same exact page set below `/docs/` for the unified public site.
2. `docs/site/zh-CN/` and `docs/site/ja/` each mirror exactly `index.md`, `quickstart.md`,
   `startup-modes.md`, `configuration.md`, `first-run.md`, and `faq.md`.
3. VitePress native locales provide `en-US`, `zh-CN`, and `ja` language metadata plus localized
   navigation, sidebar, site title, description, and language labels.
4. Locale selection is explicit. The site does not inspect browser language, redirect the root,
   persist a locale preference outside VitePress behavior, or add a custom language component.
5. The three variants share `docs/site/public/` assets. Localized images are not introduced by
   this ADR.
6. Relative page links remain within the selected locale. Localized headings update their local
   fragment links where necessary; commands, paths, URLs, environment variables, example values,
   code fences, and product UI labels remain operationally exact.
7. Each localized page identifies English as the authoritative source. Translation attribution
   must describe the tools actually used and must not claim a tool or model that did not perform
   the translation.
8. Contract checks require each locale to contain exactly the six authorized pages, require
   locale-relative Markdown targets to exist, and require every localized Configuration page to
   cover the complete source and tagged-release `.env.example` key set.
9. Local development, static build, preview, and the existing optional build-only CI check remain
   the only active delivery surfaces.

## Non-goals

1. Before ADR-0026 activation: GitHub Pages, a public documentation URL, README online-doc links,
   custom domains, or VitePress project-path `base` configuration. ADR-0026 now authorizes the
   bounded `latentrun/SurgePilot` Pages target and project base; a custom domain remains excluded.
2. A seventh user page, API or AI Skill reference sections, contributor architecture navigation,
   or exposure of `docs/sdd` and `docs/prd` in user navigation.
3. Multi-version documentation, automatic translation, browser-language redirection, translation
   management services, or a separate external-link checker.
4. Product UI localization, API message localization, or changes to deployment behavior.

## Consequences

1. Chinese and Japanese readers can use the complete six-page user guide from native VitePress
   locale navigation without changing existing English links.
2. Each English content change now has two translation consumers that require review and
   synchronization.
3. Exact page-set and Configuration-key tests detect structural and operational drift, while
   language quality remains a human review responsibility.
4. The static build expands from six pages to eighteen pages without adding a service, dependency,
   deployment target, or publication workflow.

## References

- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- `docs/site/.vitepress/config.mts`
- `tests/contract/test_env_example_drift.py`

## Verification Backfill

The reconstructed ADR-0025 verification is recorded in
`docs/sdd/slices/P2-07-public-launch-github-pages-seo.md` §14. `tests/contract/test_user_docs_locales.py`
enforces the exact six-page English page set and the exact `zh-CN` and `ja` mirrors, requires
locale-relative Markdown targets to resolve, and keeps every localized Configuration page aligned
with the source and tagged-release `.env.example` key set. `docs/site/package.json` binds the
VitePress build to `docs/site/tests/verify-built-site.mjs`, which confirms the localized pages emit
meaningful static HTML with unique metadata, self-canonical URLs, and reciprocal
`en`/`zh-CN`/`ja`/`x-default` alternates below the `/docs/` project base. Theme configuration and
navigation stay explicit per locale with no browser-language detection or root redirect.
