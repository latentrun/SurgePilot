# P2-07 Public Launch Implementation Plan

> Executable behavior follows test-driven development. All private-stage work is delivered as
> sequential review checkpoints so the owner can accept or revert the complete launch preparation
> atomically.

**Goal:** Prepare the complete private-stage `latentrun/SurgePilot` public launch: one static
VitePress marketing/docs site, crawlable SEO output, self-hosted Web indexing isolation,
repository/authorship evidence, launch assets, and public-readiness gates.

**Architecture:** `docs/site` remains the only public-site package. A custom VitePress marketing
layout owns the project root while the exact localized user guides move below `/docs/`; one site
configuration module owns the future origin/base and page metadata. The self-hosted React product
remains separate and receives only an early `noindex` policy. Public visibility, the baseline tag,
tagged Release publication, and Pages deployment activation remain manual launch gates.

**Tech Stack:** VitePress 1.6, Vue 3 theme components, TypeScript, CSS, Node build assertions,
pytest contract checks, Nginx, GitHub Actions, Markdown, Playwright browser inspection.

## Global Constraints

- Target repository: `latentrun/SurgePilot`.
- Future public origin: `https://latentrun.github.io/SurgePilot/` with project base `/SurgePilot/`.
- English-first marketing; English documentation remains authoritative with exact `zh-CN` and
  `ja` six-page mirrors.
- Primary conversion action: legitimate **Star on GitHub**.
- Human role: product intent, requirements discussion, product use, usage feedback, and result
  acceptance.
- AI-agent role: product/process design, governance and quality gates, PRD/SDD/ADR/Slice,
  architecture/contracts, implementation/tests, verification repair, deployment, and release
  assets.
- The strong AI-authorship claim is bound to one launch-time immutable semantic-version tag; until
  launch freeze, no tag is claimed.
- Future contributors may use any workflow and do not need AI provenance.
- No hosted-service, pricing, signup, fabricated benchmark/adoption/status/Star, automatic
  translation, custom-domain, blog/CMS, or programmatic-SEO promise.
- Private CI may build and validate Pages output but must not have Pages deployment permissions or
  invoke a Pages deployment action.
- Actual repository visibility, organization migration, tag/Release publication, and Pages
  deployment activation remain outside this private-stage implementation.

---

### Task 1: Align governance with single-checkpoint delivery

**Files:**
- Modify: `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- Modify: `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`
- Modify: `docs/sdd/public-launch-github-pages-and-star-growth-plan.md`
- Modify: `docs/sdd/README.md`

- [ ] Record the owner's decision that private-stage checkpoints use sequential commits rather than
  multiple dependent pull requests.
- [ ] Preserve the same launch gates and keep public activation manual.
- [ ] Replace the governance-only plan index with this full implementation plan.
- [ ] Run `git diff --check`.

### Task 2: Restructure routes and establish one site configuration

**Files:**
- Move: `docs/site/{index,quickstart,startup-modes,configuration,first-run,faq}.md` user-guide
  content to `docs/site/docs/`
- Move: `docs/site/{zh-CN,ja}/` to `docs/site/docs/{zh-CN,ja}/`
- Create: `docs/site/.vitepress/site.ts`
- Modify: `docs/site/.vitepress/config.mts`
- Modify: `tests/contract/test_user_docs_locales.py`
- Create: `docs/site/tests/verify-built-site.mjs`
- Modify: `docs/site/package.json`

**Interfaces:**
- Produce: `PUBLIC_SITE.origin`, `PUBLIC_SITE.base`, `PUBLIC_SITE.repository`, and route helpers in
  `site.ts`.
- Produce: exact routes `/`, `/docs/`, `/docs/{page}`, `/docs/zh-CN/{page}`, and
  `/docs/ja/{page}` under the VitePress project base.
- Consume: existing six-page locale and Configuration drift contracts.

- [ ] Write failing Python locale/page-set assertions for the new `docs/` source tree.
- [ ] Run the focused pytest and confirm it fails because the route tree has not moved.
- [ ] Write failing built-site assertions for the project base, expected output pages, internal
  links, one H1 per page, and absence of host-root asset assumptions.
- [ ] Run the docs test and confirm it fails for missing routes/configuration.
- [ ] Move the existing guide content and implement the centralized site/base configuration.
- [ ] Run locale and docs build checks to green.
- [ ] Complete the route/base checkpoint.

### Task 3: Build the static Star-first marketing homepage

**Files:**
- Create: `docs/site/.vitepress/theme/MarketingHome.vue`
- Modify: `docs/site/.vitepress/theme/index.ts`
- Replace: `docs/site/index.md`
- Modify: `docs/site/.vitepress/theme/custom.css`
- Delete: `docs/site/public/surgepilot-hero.png`
- Modify: `docs/site/tests/verify-built-site.mjs`

**Interfaces:**
- Produce: a meaningful SSR marketing document at `/SurgePilot/` with one H1.
- Consume: `PUBLIC_SITE` links and the existing SurgePilot logo.

- [ ] Add failing built-output assertions for the AI-baseline hook, adjacent human/AI boundary,
  evidence links, distributed-system proof, and Star/Docs/Releases CTAs.
- [ ] Assert that marketing output contains no Log in, Sign up, hosted-service, pricing, or disabled
  community targets; synthetic throughput, Run rows, and Distributed mesh values require adjacent
  example/non-live/non-benchmark labels.
- [ ] Run the docs test and confirm the missing marketing contract fails.
- [ ] Implement the custom semantic layout using a dark industrial control-room direction,
  cyan/magenta signal accents, asymmetrical evidence panels, responsive navigation, accessible
  focus states, and the repository-owner-approved full-motion desktop presentation.
- [ ] Replace the 2 MB hero dependency with CSS/vector structure and optimized real assets.
- [ ] Run the docs build assertions to green and complete the marketing checkpoint.

### Task 4: Implement technical SEO, localization alternates, and asset budgets

**Files:**
- Create: `docs/site/.vitepress/seo.ts`
- Modify: `docs/site/.vitepress/config.mts`
- Generate: `docs/site/.vitepress/config.mts` build output `robots.txt` from `PUBLIC_SITE`
- Create: `docs/site/public/surgepilot-architecture.jpg`
- Create: `docs/site/tests/verify-browser.mjs`
- Modify: `docs/site/package.json`, `pnpm-lock.yaml`, and `.github/workflows/pages-build.yml`
- Modify: all eighteen documentation frontmatter blocks only where localized metadata is required
- Modify: `docs/site/tests/verify-built-site.mjs`

**Interfaces:**
- Produce: unique title/description, self-canonical, Open Graph, Twitter Card, reciprocal
  `hreflang` plus `x-default`, and supportable JSON-LD for every indexable page.
- Produce: canonical-only `sitemap.xml` and project-scoped `robots.txt`.
- Enforce: total/individual public asset budgets and optimized social image dimensions.

- [ ] Add failing output assertions for metadata uniqueness, canonical URLs, locale reciprocity,
  `x-default`, JSON-LD parseability, sitemap allowlist, robots sitemap reference, 404 `noindex`,
  image alternatives, and asset budgets.
- [ ] Run the docs test and confirm the new SEO assertions fail.
- [ ] Implement route metadata/alternate clusters through one typed SEO source and VitePress build
  hooks; do not duplicate origin/base literals through page files.
- [ ] Generate the social preview from the reviewed marketing visual, keep it below the budget, and
  ensure dimensions are explicit.
- [ ] Build and inspect output to green; complete the SEO/assets checkpoint.

The production docs test also launches a local VitePress preview and uses a JavaScript-capable
headless browser to validate rendered canonical metadata, alternates, JSON-LD, and public-page
content. CI installs the Chromium runtime before running that check.

### Task 5: Isolate self-hosted Web indexing

**Files:**
- Create: `tests/contract/test_p2_07_public_launch.py`
- Modify: `apps/web/index.html`
- Modify: `apps/web/nginx.conf`

**Interfaces:**
- Produce: HTML `robots`/`googlebot` directives and an `X-Robots-Tag` response policy before React
  routing/session restoration.
- Preserve: all existing landing, login, registration, protected-route, and auth behavior.

- [ ] Write failing contract assertions for the HTML and Nginx policy, including the absence of a
  blocking self-hosted `robots.txt` rule.
- [ ] Run the focused test and confirm it fails because `noindex` is absent.
- [ ] Add the minimal meta/header policy without touching product routing.
- [ ] Run the contract and existing Web marketing/auth tests to green; complete the indexing
  checkpoint.

### Task 6: Publish accurate authorship and community evidence

**Files:**
- Create: `AI-AUTHORSHIP.md`
- Create: `LICENSE`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `README.ja.md`
- Modify: `tests/contract/test_p2_07_public_launch.py`

**Interfaces:**
- Produce: a precise original-baseline claim, human/AI responsibility table, evidence map, baseline
  tag state, and contributor policy that accepts human- or AI-authored work.

- [ ] Add failing contract assertions for the role boundary, relative evidence links, future target
  URLs, community files, MIT license, no unsupported production/adoption claims, and no requirement
  for contributor AI provenance.
- [ ] Run the focused test and confirm the public-readiness metadata is missing or stale.
- [ ] Rewrite the README first viewport for Star conversion while preserving operational detail.
- [ ] Add the evidence/community files and synchronize the concise localized README opening copy.
- [ ] Run focused contracts and localized-link checks to green; complete the evidence checkpoint.

### Task 7: Prepare demo, social, and launch materials

**Files:**
- Create: `docs/launch/demo-recording-guide.md`
- Create: `docs/launch/public-launch-runbook.md`
- Create: `docs/launch/community-launch-drafts.md`
- Create: `docs/launch/repository-metadata.md`
- Modify: `tests/contract/test_p2_07_public_launch.py`

**Interfaces:**
- Produce: reproducible 60–120 second recording instructions, secret-redaction checklist, ffmpeg
  conversion commands, English-first channel-specific drafts, GitHub About/topics/social-preview
  settings, and the final coordinated launch sequence.

- [ ] Add failing contract assertions for exact launch artifacts and required safety/claim wording.
- [ ] Run the focused test and confirm the launch assets are absent.
- [ ] Write executable command-by-command guides without claiming that an unrecorded video exists.
- [ ] Ensure launch drafts link to evidence and contain no fabricated metrics or mass-posting plan.
- [ ] Run the focused contract to green and complete the launch-material checkpoint.

### Task 8: Add private build CI and public-readiness audit evidence

**Files:**
- Create: `.github/workflows/pages-build.yml`
- Create: `docs/launch/public-readiness-audit.md`
- Modify: `tests/contract/test_p2_07_public_launch.py`

**Interfaces:**
- Produce: main-branch build-only validation with read-only repository permissions.
- Produce: recorded tree/history/privacy/license/author-metadata review and redacted results.

- [ ] Add failing workflow assertions: no `pages: write`, no `id-token: write`, no
  `actions/deploy-pages`, no public deployment environment, and no tag/release trigger.
- [ ] Run the focused test and confirm the workflow is absent.
- [ ] Implement pnpm install plus docs build/test artifact validation with `contents: read` only.
- [ ] Run tracked-tree and repository scans for credential filenames, secret material, private
  endpoints/IPs, personal paths, author emails, and asset licenses; record only redacted findings
  and required owner decisions.
- [ ] Run contracts to green and complete the readiness checkpoint.

### Task 9: Browser and repository acceptance

**Files:** all files touched by P2-07 private implementation.

- [ ] Run the VitePress production build and preview at the actual `/SurgePilot/` base.
- [ ] Use a JavaScript-capable browser to inspect desktop/mobile layout, keyboard focus, reduced
  motion, canonical/hreflang, and parsed JSON-LD.
- [ ] Capture and display the reviewed marketing screenshot and social preview.
- [ ] Run focused pytest, Web tests/build, docs tests/build, workflow YAML parsing, link/reference
  scans, `git diff --check`, and `make verify`.
- [ ] Record the complete private-stage implementation in the review description.
- [ ] Wait for GitHub checks and leave public activation unperformed for the owner's final review.

---

### Task 10: Rebase the public landing on the product Landing visual system

**Owner review:** Accepted. The product Landing is the visual source of truth. The
Pages landing remains a separate VitePress implementation, but it must preserve the product
Landing's dark dot-grid composition, typography, glass surfaces, responsive section rhythm, and
signature motion. The existing P2-07 directory, SEO, evidence, truthfulness, and public-activation
boundaries remain accepted.

**Files:**
- Modify: `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- Modify: `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`
- Modify: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Modify: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Modify: `AGENTS.md`
- Modify: `apps/web/AGENTS.md`
- Modify: `apps/web/src/features/marketing/pages/stitch-landing-markup.ts`
- Modify: `apps/web/src/features/marketing/pages/landing-page.tsx`
- Modify: `apps/web/src/features/marketing/landing-markup.test.ts`
- Modify: `apps/web/src/features/marketing/landing-page.test.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Replace: `docs/site/.vitepress/theme/MarketingHome.vue`
- Create: `docs/site/.vitepress/theme/marketing/marketing-markup.ts`
- Create: `docs/site/.vitepress/theme/marketing/marketing.css`
- Copy only required local font assets beneath `docs/site/.vitepress/theme/marketing/fonts/`
- Create: `docs/site/postcss.config.mjs`
- Create: `docs/site/tailwind.config.mjs`
- Modify: `docs/site/.vitepress/theme/index.ts`
- Modify: `docs/site/.vitepress/theme/custom.css`
- Modify: `docs/site/package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `docs/site/tests/verify-built-site.mjs`
- Modify: `tests/contract/test_p2_07_public_launch.py`

**Interfaces:**
- The self-hosted Landing keeps `/login`, `/register`, and auth redirect behavior while activating
  the exact future Docs and repository targets.
- The Pages Landing keeps Star as the primary action and has no Log in or Sign up action.
- Both surfaces use truthful `OPEN SOURCE · SELF-HOSTED` labels and preserve the original animated
  dashboard/Recent Test Runs/Distributed load mesh only beside explicit
  UI-demonstration/example/non-live/non-benchmark wording.
- Pages continues to emit meaningful SSR HTML and to consume `PUBLIC_SITE` plus VitePress base
  helpers without importing React, auth, API-client, or Router modules.

- [ ] Amend ADR-0026, the P2-07 Slice, Foundation UI/workflow rules, and synced Agent instructions
  before changing the self-hosted Landing links.
- [ ] Add failing Web and Pages assertions for active Docs/GitHub targets, restored and explicitly
  labelled synthetic dashboard/Run/Distributed mesh presentation, product visual markers, and SSR
  evidence.
- [ ] Update the product Landing copy and targets without changing authentication routing.
- [ ] Port the approved product Landing visual composition and signature CSS/SVG motion to the
  independent VitePress marketing layout.
- [ ] Integrate the existing AI responsibility boundary, repository evidence targets, Star, Docs,
  Release, Quickstart, SEO, canonical, social, and schema contracts into that visual system without
  replacing the original Recent Test Runs panel.
- [ ] Preserve the product Landing's runtime counter intervals and full signature motion on both
  desktop-first surfaces, omit Landing-scoped reduced-motion suppression, and retain the existing
  3 MB total / 150 KB emitted-asset budgets.
- [ ] Run only focused Web Landing tests/build, focused P2-07 contracts, docs tests/build, and
  desktop browser inspection. Per owner direction, do not run `make verify` for this
  landing-only review cycle.
- [ ] Complete the checkpoint without public activation or merge.
