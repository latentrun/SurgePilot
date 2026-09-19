# SurgePilot SDD

This directory is used to place SurgePilot engineering design documents.

## Document lifecycle

- **Draft**: under development; it does not authorize implementation unless an explicit user
  decision approves that design task.
- **Accepted**: approved implementation authority within the document's stated scope.
- **Superseded**: replaced and required to name its replacement.

Release-baseline membership is recorded separately against an immutable tag. Editing lifecycle
metadata does not grant approval; see `ai-development-governance-optimization-design.md` and the
v1.0.0 lifecycle audit.

## Document entry

- `ai-development-governance-optimization-design.md` — accepted AI contribution governance and
  instruction-architecture design for Issues #37-#41.
- `v1.0.0-governing-document-lifecycle-audit.md` — lifecycle and released-baseline audit anchored
  to the immutable v1.0.0 tag.
- `00-product-scope-and-priority.md`
- `01-architecture-overview.md`
- `02-repo-structure-and-dev-workflow.md`
- `03-domain-model-overview.md`
- `04-api-contract-guidelines.md`
- `05-runner-protocol-and-run-state-machine.md`
- `06-security-permission-workspace.md`
- `07-storage-artifacts-minio.md`
- `08-frontend-routing-and-ui-rules.md`
- `09-testing-and-acceptance-strategy.md`

## Proposed plans

- `public-launch-github-pages-and-star-growth-plan.md` : non-authorizing proposal for the
  `latentrun/SurgePilot` public launch, unified GitHub Pages site, SEO, AI-authorship evidence, and
  legitimate GitHub Star growth.

## Active delivery plans

- `p2-07-public-launch-implementation-plan.md` : complete private-stage implementation in
  sequential review checkpoints inside public launch checkpoint; public activation remains a later manual gate.

## Active public-launch governance

- `adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- `slices/P2-07-public-launch-github-pages-seo.md`

## Subdirectory

- `adr/` : Architecture decision record.
- `slices/` : P0/P1/P2 functional Slice SDD.
