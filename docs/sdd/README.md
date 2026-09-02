# SurgePilot Foundation SDD

These documents translate the product requirements into the initial engineering baseline. They define cross-cutting boundaries; feature-level endpoint fields, migrations, UI details, and acceptance cases belong in later Slice SDDs.

## Reading order

1. `../prd/PRD.md`
2. `00-product-scope-and-priority.md`
3. `01-architecture-overview.md`
4. `02-repo-structure-and-dev-workflow.md`
5. `03-domain-model-overview.md`
6. `04-api-contract-guidelines.md`
7. `05-runner-protocol-and-run-state-machine.md`
8. `06-security-permission-workspace.md`
9. `07-storage-artifacts-minio.md`
10. `08-frontend-routing-and-ui-rules.md`
11. `09-testing-and-acceptance-strategy.md`

Accepted decisions in `adr/` explain the initial architectural trade-offs. The PRD controls product meaning and scope; the scope gate controls milestone boundaries; accepted ADRs control the decisions they record; the remaining foundation SDDs control their named technical concerns. A lower-precedence document must be corrected when it conflicts with a higher-precedence source.

## Initial ADR index

- `adr/ADR-0001-monorepo.md`
- `adr/ADR-0002-runner-independent-app.md`
- `adr/ADR-0003-p0-minio-only.md`
- `adr/ADR-0004-p0-manual-single-node-only.md`
- `adr/ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md`
- `adr/ADR-0006-p0-separate-api-worker.md`
