# ADR-0023 Remove Scenario Execution Preview

- Status: Accepted
- Scope: Remove the Scenario Generated YAML Preview while retaining the Test Plan Generated YAML Preview

## Context

P1-04 originally specified read-only Generated YAML Preview surfaces for both Scenario and Test Plan. The implemented Scenario Designer intentionally does not expose that surface, while the Scenario preview API and generated contract remained available and the P1-04 browser acceptance test still expected the hidden action. This left the accepted design, API contract, Web behavior, and test suite inconsistent.

The Test Plan editor already provides the useful execution-level preview because it includes the saved Scenario references, run type, resource configuration, load settings, Env Group, and SLA context. A second Scenario-only YAML surface duplicates that diagnostic concept without the complete execution context.

## Options Considered

### Option A: Restore Scenario Generated YAML Preview

Rejected. It would duplicate the Test Plan surface and add a Scenario-specific Env Group selection solely to construct a partial execution view.

### Option B: Retain Test Plan Preview and remove Scenario Preview

Accepted. Scenario remains a structured visual editor with Debug Run support. Test Plan remains the single user-facing Generated YAML Preview surface.

### Option C: Keep the Scenario API but continue hiding the Web surface

Rejected. A callable generated contract for a deliberately unsupported product surface would preserve the same governance inconsistency and unnecessary maintenance burden.

## Decision

1. Remove `GET /api/v1/scenarios/{scenarioId}/execution-preview` and its generated client operation.
2. Do not show `Generated YAML Preview`, `Preview environment`, or `Preview YAML` in the Scenario Designer.
3. Keep `GET /api/v1/test-plans/{testPlanId}/execution-preview` and the Test Plan read-only Generated YAML Preview unchanged.
4. Keep Scenario Debug Run, Scenario validation, Taurus document generation, Env Group input, and runtime execution behavior unchanged.
5. Keep the shared safe YAML projection used by Test Plan Preview; do not add a replacement Scenario preview surface.
6. Update P1-04, P1-09, P2-03, generated contracts, and acceptance tests to express this single-surface boundary.
7. No historical compatibility route or deprecation layer is required during the current development stage.

## Consequences

1. Scenario clone, archive, tags, Global Configuration, validation, Debug Run, and execution behavior remain available.
2. Test Plan is the only product surface that displays Generated YAML Preview.
3. `ExecutionPreviewResponse`, preview warnings, redaction behavior, and `INVALID_EXECUTION_PREVIEW_MODE` remain because Test Plan Preview still uses them.
4. Scenario endpoint-specific API and contract tests are removed; Scenario tests assert the endpoint and Web action are absent.
5. Test Plan Preview tests continue to cover read-only rendering and secret-value redaction.

## Related ADRs

- `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`

## References

- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/slices/P1-04-scenario-testplan-polish.md`
- `docs/sdd/slices/P1-09-scenario-global-configuration.md`
- `docs/sdd/slices/P2-03-env-group-secret.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
