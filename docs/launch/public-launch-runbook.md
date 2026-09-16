# SurgePilot Public Launch Runbook

- Target: `latentrun/SurgePilot`
- Public site: `https://latentrun.github.io/SurgePilot/`
- Status: manual runbook; no action is pre-approved

**Do not run any public-activation step without repository-owner approval.** Repository visibility, release publication, package visibility, metadata, and Pages deployment are separate gates.

Use one launch record for the operator, UTC time, reviewed launch candidate, check URLs, and result for every checkbox. Never paste credentials or unredacted audit output into the record.

## Phase 0 — assign control and freeze

- [ ] Name one launch operator and one reviewer; confirm both can stop the launch.
- [ ] Freeze private writes and confirm the reviewed launch candidate is unchanged.
- [ ] Confirm `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `AI-AUTHORSHIP.md` are present.
- [ ] Confirm no public release or baseline claim has been published.
- [ ] Record a rollback contact and retain the approved private recovery copy.

Stop if the candidate changes after the freeze.

## Phase 1 — privacy, license, and security gate

- [ ] Review `public-readiness-audit.md` and resolve every blocker.
- [ ] Review author metadata, image/font/source licenses, generated assets, credentials, personal data, private endpoints, and unsafe paths.
- [ ] Rotate any credential that may have been exposed.
- [ ] Confirm the repository identity is `latentrun/SurgePilot` and package images use `ghcr.io/latentrun`.

Do not continue while any privacy, security, or license decision is unresolved.

## Phase 2 — private organization preparation

- [ ] Confirm the `latentrun` organization and `SurgePilot` repository are ready, with tested owner/admin recovery access.
- [ ] Keep public visibility disabled while settings, environments, secrets, variables, Actions, vulnerability reporting, and package access are reviewed.
- [ ] Confirm repository, GHCR, installer, README, release-manifest, and Pages URLs agree.

## Phase 3 — reviewed-candidate verification

From a clean checkout of the reviewed launch candidate, run the project’s documented setup, contract, verification, documentation, and release-validation checks.

- [ ] Required checks are green for the same reviewed candidate.
- [ ] Preview the production docs at `/SurgePilot/` on desktop and mobile.
- [ ] Check focus, motion, canonical/hreflang, JSON-LD, sitemap, robots, and 404 `noindex` behavior.
- [ ] Confirm self-hosted Web HTML and Nginx return `noindex`.
- [ ] Inspect the non-secret release-validation summary and artifacts.

Any candidate change returns to the applicable privacy or verification gate.

## Phase 4 — release readiness

- [ ] Owner selects the baseline release identity only after readiness review.
- [ ] Record the matching release URL and verification evidence in `AI-AUTHORSHIP.md`.
- [ ] Inspect the installer, bundle, checksums, manifests, both Runtime architectures, image digests, and release asset list.
- [ ] On a clean supported host, test the user-local bundle and interactive `./surgepilot up` path.
- [ ] Confirm anonymous package access and absence of secrets or ignored local state.

## Phase 5 — coordinated public activation

This phase needs fresh owner approval after Phases 0–4 are green:

1. Enable public visibility for `latentrun/SurgePilot`.
2. Verify anonymous repository, community files, and source access.
3. Publish the reviewed release and verify installer, bundle, checksums, manifests, Runtime assets, and anonymous GHCR pulls.
4. From a clean supported host, verify anonymous installation, first Admin creation, Load Node readiness, one authorized low-load Run, report, and shutdown.
5. Enable Pages with the separately reviewed deployment source.
6. Verify the marketing home, three documentation roots, assets, canonical URLs, sitemap, and robots file anonymously.
7. Apply the reviewed values from [`repository-metadata.md`](repository-metadata.md).
8. Publish only drafts whose links resolve; add a demo URL only after the recording guide passes.

## Phase 6 — first 72 hours

- [ ] Watch Actions, Pages, release downloads, anonymous install reports, issues, and security reports without publishing private logs.
- [ ] Answer questions with repository evidence and correct misleading wording.
- [ ] Record observations only from real GitHub UI or approved analytics; do not manufacture success claims.
- [ ] Triage contributions under `CONTRIBUTING.md`; no AI provenance is required.

## Rollback

Pause promotion if secrets, license violations, broken anonymous installation, misleading claims, or unsafe defaults appear. Correct or disable the affected surface, make unsafe packages unavailable where possible, rotate credentials, and re-enter at the earliest invalidated phase. Preserve investigation evidence and explain corrections transparently.
