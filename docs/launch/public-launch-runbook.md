# SurgePilot Public Launch Runbook

- Target: `latentrun/SurgePilot`
- Public site: `https://latentrun.github.io/SurgePilot/`
- Status: manual runbook; no action in this document is pre-approved

> **Do not run any public-activation step without the repository owner's approval.** Repository
> transfer, public visibility, immutable tagging, Release publication, package
> visibility, and GitHub Pages deployment are separate irreversible or externally visible gates.

Use one launch record to capture the owner, UTC timestamp, candidate commit, commands, check URLs,
and result for every checkbox. Never paste credentials or unredacted audit output into that record.

## Phase 0 — assign control and freeze

- [ ] Name one launch operator and one reviewer; confirm both can stop the launch.
- [ ] **Freeze private writes** and record the candidate identifier, working-tree status, open
  reviews, and branch protection decision.
- [ ] Confirm the candidate contains `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, and `AI-AUTHORSHIP.md`.
- [ ] Confirm no baseline tag or public Release has been claimed yet.
- [ ] Record a rollback contact and keep a private backup of the reviewed Git refs.

Stop if the working tree changes after the freeze.

## Phase 1 — privacy, license, and repository gate

- [ ] Review `docs/launch/public-readiness-audit.md` and resolve every blocker.
- [ ] Review every privacy and provenance finding in context; do not make an automated change from
  a raw pattern match.
- [ ] Re-run the repository scans after each approved candidate change.
- [ ] Verify author-name/email exposure, image/font/source licenses, and generated assets are
  acceptable for a public repository.
- [ ] Rotate any credential that may have entered the repository.

Freeze and verify the candidate again before continuing whenever a reviewed change is made.

## Phase 2 — private organization migration

- [ ] Confirm the `latentrun` organization exists, the `SurgePilot` name is free, and owner/admin
  access plus recovery methods are tested.
- [ ] Transfer or mirror the still-private repository to `latentrun/SurgePilot` while preserving
  only the approved repository state, tags, branches, and review record.
- [ ] Keep **public visibility disabled**.
- [ ] Recreate branch rules, environments, secrets, variables, Actions settings, Dependabot/code
  scanning settings, and private vulnerability reporting intentionally; do not assume transfer
  preserves each setting.
- [ ] Audit and update owner-bound repository/package literals. In particular,
  `.github/workflows/release.yml`, `release-validation.yml`, and
  `release-package-bootstrap.yml` currently require an explicit migration review before a tag is
  allowed. Confirm the canonical repository and GHCR namespaces, installer URLs, README links,
  and release manifests all agree.
- [ ] Commit migration-only literal changes, re-review them, and record the new exact candidate.

Do not push a semantic tag while a release workflow still expects the previous repository or GHCR
namespace.

## Phase 3 — exact-candidate verification

From a clean clone of the still-private target repository, check out the exact candidate commit:

```bash
make setup
make generate-contracts
make contracts-stale-check
make verify
pnpm --filter @surgepilot/docs test
uv run --all-packages pytest tests/contract/test_p2_07_public_launch.py -q
```

- [ ] All required GitHub checks are green on the same commit.
- [ ] Preview the production docs build at the real `/SurgePilot/` base on desktop and mobile.
- [ ] Check keyboard focus, reduced motion, canonical/hreflang, JSON-LD, sitemap, robots, and the
  404 `noindex` result.
- [ ] Confirm self-hosted Web HTML and Nginx still return `noindex`.
- [ ] Re-run the release validation workflow and retain its non-secret artifact/check summary.

Any candidate change returns to Phase 1 or Phase 3 according to its risk.

## Phase 4 — select the original baseline

- [ ] Owner selects an unused semantic version only after Release readiness review.
- [ ] Update `AI-AUTHORSHIP.md` so the pending fields contain the exact candidate, **immutable
  baseline tag**, matching Release URL, and verification record.
- [ ] Review the diff and rerun Phase 3.
- [ ] Create the signed or annotated tag locally on exactly that commit; verify
  `git rev-list -n1 <tag>` and **do not push it yet**.
- [ ] Confirm `.github/workflows/release.yml` points at the final repository and package
  namespaces and that pushing this tag is the reviewed Release trigger.

Pushing the tag later triggers the existing create-only release pipeline. Do not manually replace
a failed Release or mutable image tag; diagnose, use a new reviewed version if required, and
preserve the failure evidence.

## Phase 5 — private Release-readiness gate

- [ ] Run the complete `release-validation.yml` path on the exact candidate and retain its
  non-secret summary.
- [ ] Inspect the validation bundle, installer, checksums, manifests, both Runtime architectures,
  image digests, and expected `release.yml` asset list.
- [ ] On a clean supported host and empty user-local install root, test the validated local bundle
  and interactive `./surgepilot up` path. This proves the candidate package, not anonymous GitHub
  access.
- [ ] Confirm source archives and validation artifacts do not contain secrets or ignored local
  state.
- [ ] Confirm the organization permits the final GHCR packages to be made anonymously readable by
  the Release workflow.

Stop before repository visibility changes if any candidate asset or local install path fails.

## Phase 6 — coordinated public activation

This phase needs a fresh owner approval after Phases 0–5 are recorded green.

1. Change repository **public visibility** for `latentrun/SurgePilot`.
2. Verify anonymous README, repository state, community files, and source access immediately.
3. Push the reviewed immutable tag and wait for `release.yml` to publish the create-only Release.
4. From a logged-out browser, download the installer, bundle, checksums, manifests, and Runtime
   assets; verify anonymous GHCR digest pulls. From a clean supported host, verify **anonymous
   installation**, first Admin creation, Load Node readiness, one authorized low-load Run, report,
   and `surgepilot down`.
5. Enable GitHub Pages using the separately reviewed deploy workflow/source. The private-stage
   `pages-build.yml` is build-only and is not a deployment workflow.
6. Wait for **GitHub Pages** deployment, then verify the marketing home, all three documentation
   roots, assets, canonical URLs, sitemap, and `robots.txt` anonymously.
7. Apply the reviewed About/topics/social-preview values from
   [`repository-metadata.md`](repository-metadata.md).
8. Publish only the channel drafts whose links now resolve. Add the reviewed demo URL only if a
   real recording passed [`demo-recording-guide.md`](demo-recording-guide.md).

The goal is a short coordinated window, not simultaneous blind changes. Verify each surface before
driving traffic to it.

## Phase 7 — first 72 hours

- [ ] Watch Actions, Pages, Release downloads, anonymous install reports, issues, and security
  reports without publishing private logs.
- [ ] Answer technical questions with repository evidence; correct misleading launch wording.
- [ ] Record referrer/Star observations only from GitHub's real UI or approved analytics. Do not
  manufacture a baseline or success claim.
- [ ] Triage contributions under `CONTRIBUTING.md`; no AI provenance is required.

## Rollback

Pause promotion immediately if secrets, private repository content, license violations, broken anonymous
installation, misleading claims, or unsafe load-test defaults are discovered.

1. Remove or correct social posts that send users to the affected surface.
2. Disable GitHub Pages if its artifact or metadata is unsafe.
3. Make a vulnerable Release unavailable and make packages private when possible, without deleting
   evidence needed for investigation.
4. If repository content itself is unsafe, make the repository private and begin credential
   rotation plus an owner-approved remediation.
5. Do not move or retarget the immutable baseline tag. Correct the record transparently with a new
   commit/version and document what changed.
6. Re-enter this runbook at the earliest invalidated phase.
