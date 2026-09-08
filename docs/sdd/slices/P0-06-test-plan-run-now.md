# P0-06: Test Plan and Run Now

- Documentation status: Draft v1
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/slices/P0-06-test-plan-run-now.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Run / Runner Source: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security / Workspace Source: `docs/sdd/06-security-permission-workspace.md`
- Frontend Source: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Optional local Taurus reference: developer-supplied files under ignored `docs/reference/taurus/` may be used for Taurus/JMeter details, but they are not required in a fresh repository checkout.
- Current delivery target: P0 only
- Scope of application: Test Plan CRUD, Scenario Orchestration, Load Settings, SLA minimum subset, Manual single-node Resource Configuration, Test Plan Debug, Run Now, Test Plan execution snapshot, Taurus execution / passfail mapping, AI Coding, Code Review, Test Acceptance

---

## 1. Goal

P0-06 delivers a **Test Plan** that users can save, reuse, and execute manually.

Once completed, users can within the current Workspace:

1. Create, edit, list view and delete Test Plan;
2. Select the optional Env Group, Run Mode, Pool Type and a manually selected Idle Load Node;
3. Arrange one or more saved Visual Scenarios and configure Load Settings separately for each Scenario item;
4. Configure P0 minimum SLA Rules;
5. Initiate Test Plan Debug Run;
6. Launch Standard Run Now;
7. After Run is created, jump to `/runs/:runId`, and P0-07 will fully present the Run Report, artifacts and Validity.

The core results of P0-06 are:

```text
Test Plan List
  -> Create Test Plan
  -> Test Plan Editor
  -> Select Env Group, Run Mode, one Idle Load Node, Scenario items, Load Settings, SLA Rules
  -> Save
  -> Debug or Run Now
  -> POST /api/v1/runs
  -> Run(initializing) + immutable Test Plan Snapshot + node lease
  -> Redirect /runs/:runId
```

P0-06 is not an API Catalog, not a Taurus YAML editor, not a scheduling system, and not a multi-node resource orchestrator.

---

## 2. PRD Trace

| PRD area | P0-06 coverage |
| --- | --- |
| §4 P0 Main Link | Implement the paragraph "Create Test Plan → Manually select a single Idle Load Node → Run Now / Debug" and hand it over to P0-07 to complete the report closed loop. |
| §5.6 Test Plan | Supports P0 subset of Test Plan basic information, Global Context, Resource Configuration, Scenario Orchestration, SLA Rules and Run Actions. |
| §5.7 Load Settings | Supports per-Scenario concurrency per node, ramp-up, hold-for or iterations, throughput, steps, delay. |
| §5.8 Run | Create a Run Now for `runType=standard` and a Test Plan Debug Run for `runType=debug`, both using `sourceType=test_plan`. |
| §6.2 Routes | Implement `/test-plans`, `/test-plans/:planId`; jump to `/runs/:runId` after Run is created successfully. |
| §8.7 Test Plans | Implement list, search, label, create, edit, delete and lightweight Quick Run; Clone, Schedule, Generated YAML Preview will not enter P0. |
| §9.1 Execution main process | Create Run, Snapshot, node lease and Busy node atomically through P0-04 Run creation service. |
| §9.3 / §9.4 Run conclusion field | Test Plan Debug defaults to Invalid; Run Now defaults to Valid; P0-07 is responsible for display and manual switching. |
| §9.6 Debug Run | Test Plan Debug uses low-risk workloads and is not an official result. |
| §9.7 Resource Allocation Rules | P0 Strict Manual Single node; does not implement Auto, multi-node or queuing. |
| §9.8 Snapshot Rules | Save Test Plan, Scenario, Env Group, Dependency File, Load Settings, SLA, and Resource Request snapshots when a Run is created. |

---

## 3. Document Responsibility

### 3.1 This Slice Owns

P0-06 owns:

1. `test_plans` data model for P0 Test Plans;
2. Test Plan Scenario Orchestration item model;
3. Test Plan SLA Rule model;
4. Test Plan CRUD public APIs;
5. Env Group real reference from Test Plan and Env Group delete protection handoff;
6. Scenario real references from Test Plan and Scenario delete protection handoff;
7. full Load Settings validation and guardrails for P0 single-node execution;
8. high-concurrency soft warning and backend confirmation contract;
9. public `POST /api/v1/runs` extension for `runType=standard`, `sourceType=test_plan` Run Now;
10. public `POST /api/v1/runs` extension for `runType=debug`, `sourceType=test_plan` Test Plan Debug;
11. Run creation dedup extension for Test Plan Runs, reusing the P0-05 mechanism if already implemented;
12. immutable Test Plan Run Snapshot payload;
13. Taurus execution mapping for multiple Scenario items, sequential / parallel mode, load profile and passfail criteria;
14. Test Plan List and Test Plan Editor frontend contract;
15. tests and verification requirements for Test Plan CRUD, Load Settings, SLA, Run Now and Test Plan Debug.

### 3.2 Foundation SDDs Remain Authoritative For

| Foundation SDD | Authority retained |
| --- | --- |
| `00-product-scope-and-priority.md` | P0/P1/P2 boundaries, forbidden work, input guard requirements and P0 single-node scope. |
| `04-api-contract-guidelines.md` | URL shape, headers, OpenAPI source of truth, error envelope, pagination, CSRF and generated client rules. |
| `05-runner-protocol-and-run-state-machine.md` | Run states, Stop, callback idempotency, node lease, heartbeat timeout, force-kill and Runner protocol. |
| `06-security-permission-workspace.md` | Session, Workspace, role, permission, credential safety and audit rules. |
| `07-storage-artifacts-minio.md` | MinIO object storage, artifact path safety and artifact download / preview boundaries. |
| `08-frontend-routing-and-ui-rules.md` | React/Vite routing, UI stack, generated client usage, copy, polling and P0 routes. |
| `09-testing-and-acceptance-strategy.md` | Repository verification gates, coverage policy, contract tests, fake-runner and E2E acceptance. |

### 3.3 Prior Slice Dependencies

| Prior Slice | Dependency used by P0-06 |
| --- | --- |
| P0-01 Env Groups | Test Plan may reference one Env Group. P0-06 activates real Env Group reference counting. |
| P0-02 Dependency Files | P0-06 snapshots Dependency File metadata through referenced Scenarios. It does not add independent Test Plan file selection. |
| P0-03 Load Nodes | Test Plan stores Pool Type and one selected node; Run validates selected node is visible and Idle. |
| P0-04 Run State Machine / Runner Protocol | P0-06 calls Run creation service and relies on Stop, callback, heartbeat and node lease convergence. |
| P0-05 Visual Scenario / Debug Run | P0-06 references saved Visual Scenarios and reuses Scenario validation, Scenario revision and Taurus requests-scenario generation. |

### 3.4 Later Slice Ownership

| Later Slice | Ownership |
| --- | --- |
| P0-07 Run Report / Artifacts / Validity | Run Report UI/API, KPI summary, SLA result presentation, artifact list/download/preview and Valid / Invalid marking UI. |
| P0-08 Overview / Polish | overview cards, quick entries, cross-slice empty/error states and final P0 acceptance polish. |
| P1 Slices | Clone, API Catalog import, Schedule Run, Generated YAML Preview, reusable load profiles, Auto allocation and multi-node execution. |

---

## 4. In Scope

### 4.1 Backend API

P0-06 backend includes:

1. create, list, detail, patch and soft-delete Test Plans;
2. validate Test Plan basic fields, Env Group, resource config, Scenario items, Load Settings and SLA Rules;
3. maintain Test Plan revision for optimistic save / run safety;
4. maintain scenario reference rows for delete protection and snapshot construction;
5. activate Env Group reference check for Test Plans that still hold an Env Group FK, including soft-deleted rows;
6. build immutable Test Plan Snapshot from the latest saved Test Plan and referenced Scenario revisions;
7. validate selected Load Node is eligible for manual single-node execution;
8. calculate expected single-node concurrency and enforce soft / hard input guards;
9. create Standard Run Now through `POST /api/v1/runs` with `runType=standard`, `sourceType=test_plan`;
10. create Test Plan Debug Run through `POST /api/v1/runs` with `runType=debug`, `sourceType=test_plan`;
11. perform short-window server-side Run creation deduplication for Test Plan Runs;
12. hand created Runs to the P0-04 start request / api-worker / Runner flow.

### 4.2 Data

P0-06 adds or activates:

1. `test_plans` table;
2. `test_plan_scenario_items` table;
3. `test_plan_sla_rules` table;
4. `runs.source_type='test_plan'` product usage;
5. Run Snapshot payload sections for Test Plan, Scenario items, Env Group snapshot, Dependency File snapshot, Load Settings, SLA Rules and Resource Request.

### 4.3 Frontend

P0-06 frontend includes:

1. `/test-plans` Test Plan List page;
2. create Test Plan action from Test Plan List;
3. `/test-plans/:planId` Test Plan Editor page;
4. Basic Information, Global Context, Resource Configuration, Scenario Orchestration, SLA Rules and Actions sections;
5. per-Scenario Load Settings editor;
6. one selected Idle Load Node selector;
7. high-concurrency confirmation UX;
8. Save, Debug and Run Now actions;
9. light Quick Run from Test Plan List only when the saved plan is runnable;
10. redirect to `/runs/:runId` after successful Test Plan Debug or Run Now;
11. English-only user copy centralized in feature copy files.

### 4.4 Taurus / JMeter Mapping

P0-06 defines how a saved Test Plan maps to Taurus execution YAML:

1. each enabled Test Plan Scenario item maps to one Taurus `execution` item;
2. each referenced Visual Scenario maps through the P0-05 requests-scenario builder;
3. `runMode=sequential` maps to `modules.local.sequential: true`;
4. `runMode=parallel` relies on Taurus default parallel execution and does not set `capacity` or `sequential`;
5. Load Settings map to Taurus `concurrency`, `ramp-up`, `hold-for`, `iterations`, `throughput`, `steps`, and `delay` where allowed by official Taurus docs and P0 runtime prerequisites;
6. Standard Run Now emits P0 SLA Rules as Taurus `reporting: [{module: passfail, criteria: ...}]` when SLA Rules are enabled;
7. Test Plan Debug does not emit passfail criteria and records `slaEvaluationMode=not_evaluated` in the snapshot.
8. each Scenario item uses an alias derived from the Test Plan item ID, so repeated references to one Scenario remain distinct;
9. each request label is bounded to 200 characters while retaining both Scenario Step ID and Test Plan item ID.

### 4.5 Tests

P0-06 requires API, contract, web and fake-runner smoke tests described in §17.

---

## 5. Out of Scope

P0-06 must not implement:

1. API Catalog;
2. OpenAPI / Swagger Spec upload;
3. API Spec detail pages;
4. Creating Test Plans from API operations;
5. cURL import;
6. OpenAPI Step auto-generation;
7. Postman Collection import;
8. original JMeter JMX upload;
9. independent script Scenario mode;
10. editable Taurus YAML;
11. generated YAML preview;
12. Test Plan clone;
13. reusable Load Profile templates;
14. Bulk Apply for Load Settings;
15. Schedule Run;
16. Scheduled Job;
17. Auto resource allocation;
18. multi-node execution;
19. Node Count;
20. Selected Nodes array;
21. resource queueing or delayed retry when selected node is unavailable;
22. live Monitoring, Grafana, InfluxDB or real-time charts;
23. Run Report, artifact download / preview or Validity UI owned by P0-07;
24. Env Group Secret type;
25. ZIP / TAR / TGZ automatic extraction;
26. automatic quarantine recovery.

Allowed P0-06 extension points:

1. enum values already required by P0-04 / P0-05 such as `runType=standard` and `sourceType=test_plan`;
2. snapshot fields needed by P0-07 if not exposed as usable P1/P2 UI;
3. nullable or extension-safe DB fields that do not activate P1/P2 behavior;
4. non-clickable documentation notes about future Clone, Schedule, Auto allocation and Generated YAML Preview.

---

## 6. Confirmed Decisions

| Area | Decision |
| --- | --- |
| Test Plan route | `/test-plans`, `/test-plans/:planId`. |
| Create UI | Create from `/test-plans`, then navigate to `/test-plans/:planId`. No separate `/test-plans/new` route is required in P0. |
| Test Plan source | P0 Test Plan references saved Visual Scenarios only. |
| Scenario count | A Test Plan may include 1 to 20 enabled Scenario items for execution. Draft save may contain 0 items. |
| Scenario item config | Each Scenario item is configured individually. Bulk Apply is not implemented in P0. |
| Run Mode | Supports `sequential` and `parallel`; default is `sequential`. |
| Env Group | Stored on Test Plan; optional for draft save; Run validates unresolved variables. |
| Resource config | Stored on Test Plan as `poolType` and one `selectedNodeId`; Run does not accept resource overrides. |
| Manual node | P0 requires exactly one visible Idle Load Node whose initialized JMeter runtime satisfies the configured P0 JMeter version at Run creation time. |
| Run Now API | `POST /api/v1/runs` with `runType=standard`, `sourceType=test_plan`. |
| Test Plan Debug API | `POST /api/v1/runs` with `runType=debug`, `sourceType=test_plan`. |
| Saved revision | Runs execute latest saved Test Plan revision only; request requires `expectedSourceRevision`. |
| Unsaved changes | Web must save first, then Run with returned revision. |
| Run creation dedup | Reuse / extend short-window dedup from P0-05; default window is 30 seconds. |
| Debug load profile | Test Plan Debug overrides every enabled item to `concurrency=1`, `iterations=1`, no ramp-up, no hold-for, no throughput, no steps and no delay. |
| Debug orchestration | Test Plan Debug executes enabled Scenario items sequentially. |
| Debug SLA | Test Plan Debug does not evaluate SLA; snapshot records `slaEvaluationMode=not_evaluated`. |
| Standard SLA | Standard Run Now evaluates enabled SLA Rules through Taurus passfail. |
| SLA count | API/data supports 0 to 5 enabled SLA Rules in P0. |
| SLA failure | SLA failure does not change Run state from `finished` to `failed`; report semantics are owned by P0-07. |
| SLA stop action | Taurus passfail `stop` may stop execution as a failed gate; if the runner exits cleanly, Run state is `finished` and SLA result is failed. |
| Validity default | `runType=standard` Test Plan Runs default to Valid; `runType=debug` Test Plan Runs default to Invalid. P0-07 owns display and mutation UI. |
| Generated YAML | Internal execution bundle artifact only; not user-editable and not previewed in P0 UI. |
| Quick Run | List page may expose Quick Run only for a saved runnable plan; otherwise it opens Editor with validation guidance. |
| Load guard | Backend is authoritative for soft and hard limits; frontend warning uses API-provided guard data. |

---

## 7. Taurus / JMeter Alignment

P0-06 Taurus/JMeter behavior should align with the Taurus/JMeter documentation. Developers may keep local reference copies under ignored `docs/reference/taurus/`, but those files are optional and are not committed.

### 7.1 Taurus Reference Topics

| Optional local reference | Contract area |
| --- | --- |
| `docs/reference/taurus/ExecutionSettings.md` | `execution` array, `concurrency`, `ramp-up`, `hold-for`, `iterations`, `throughput`, `steps`, `delay`, `scenario`, default parallel execution and `modules.local.sequential`. |
| `docs/reference/taurus/PassFail.md` | `reporting` passfail module, full-form criteria, subjects, conditions, threshold, timeframe logic and `stop` behavior. |
| `docs/reference/taurus/ConfigSyntax.md` | `${var}` environment substitution and Taurus time unit syntax. |
| `docs/reference/taurus/JMeter.md` | requests-scenario global settings, local request settings and JMeter variable behavior reused through P0-05. |
| `docs/reference/taurus/jmeter/stepping.yml` | example for `throughput`, `ramp-up`, `steps`, `hold-for` and passfail. |
| `docs/reference/taurus/jmeter/three.yml` | example for multiple executions and `modules.local.sequential`. |

### 7.2 Mapping Principles

1. SurgePilot stores product-oriented Test Plan data, not raw Taurus YAML.
2. The execution builder is the only component allowed to translate Test Plan + Scenario JSON into Taurus YAML.
3. Generated Taurus YAML is an internal execution bundle artifact; it is not a P0 product surface.
4. P0 uses Taurus `execution` items that reference P0-05-generated requests-scenarios.
5. P0 uses only local JMeter execution; Taurus cloud provisioning and distributed JMeter are forbidden in P0.
6. P0 JMeter runtime is inherited from P0-03/P0-05; the selected Load Node's configured Apache JMeter binary path is the deployment source of truth for `modules.jmeter.path`, and P0-03 initialization verifies the binary before a node becomes eligible for real Test Plan execution. The configured distribution is Apache JMeter 5.6.3 and requires Java 8 or later.
7. P0 generated YAML always disables Taurus plugin auto-detection with `detect-plugins: false`; runtime/plugin prerequisites must be satisfied by Load Node setup, not by network auto-install.
8. P0 does not use Taurus `capacity` because P0 supports only `sequential` or default parallel behavior.
9. P0 does not expose per-execution `files`, `locations`, `provisioning`, `capacity`, alternate executors, or Monitoring services.
10. P0-06 does not generate Scenario request blocks itself; `scenarios.<alias>` content is produced by the P0-05 Scenario builder and referenced by P0-06 execution items.
11. If a desired field has no clear Taurus/JMeter mapping in the local reference files, P0-06 must leave it out rather than inventing a pseudo-field.

### 7.3 Standard Run YAML Shape

Standard Run Now YAML uses this shape. The example shows the no-`steps` case; `force-ctg` switches to `true` when any Standard Run execution item emits `steps`.

```yaml
settings:
  env:
    base_url: https://example.internal
  check-updates: false
modules:
  jmeter:
    path: /opt/surgepilot/apache-jmeter/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    force-ctg: false  # no-steps example
  local:
    sequential: true
scenarios:
  scenario_01HZX3Y9M0E9W7Z6M5QK9S8P7A: {}  # produced by the P0-05 Scenario builder; abbreviated here
execution:
  - executor: jmeter
    scenario: scenario_01HZX3Y9M0E9W7Z6M5QK9S8P7A
    concurrency: 10
    ramp-up: 60s
    hold-for: 300s
reporting:
  - module: passfail
    criteria:
      - subject: p95
        condition: ">"
        threshold: 500ms
        logic: for
        timeframe: 10s
        stop: false
        fail: true
```

Rules:

1. `modules.local.sequential: true` is emitted only for `runMode=sequential` or Test Plan Debug.
2. For `runMode=parallel`, the builder omits `modules.local.sequential` because Taurus runs multiple execution items in parallel by default.
3. The builder must never emit both `modules.local.sequential` and `modules.local.capacity`.
4. Every execution item must set `executor: jmeter` and reference one generated Scenario alias.
5. Scenario aliases must be generated from safe IDs and must not contain user-controlled names directly.
6. `settings.env` is populated from the selected Env Group using P0 ordinary variable rules.
7. `settings.env` must not contain Runner token, SSH credentials, MinIO credentials or server paths.
8. JMeter path and version use the P0-03/P0-05 runtime baseline and must not be redefined independently by P0-06.
9. `modules.jmeter.detect-plugins` is always `false` in P0.
10. `modules.jmeter.force-ctg` is `false` when no emitted Standard Run execution item contains `steps`.
11. If any Standard Run execution item contains `steps`, the builder must emit `modules.jmeter.force-ctg: true`.
12. With plugin auto-detection disabled, `steps` requires preinstalled JMeter Custom Thread Groups plugin support in the selected Load Node runtime.
13. If `steps` is requested and the selected node cannot satisfy the Custom Thread Groups prerequisite, Run creation must return `TEST_PLAN_NOT_RUNNABLE` or startup must fail safely with a stable non-secret reason before executing user load.
14. P0-06 must not duplicate Scenario request mapping; `scenarios.<alias>` is P0-05 builder output.

### 7.4 Test Plan Debug YAML Shape

For Test Plan Debug, generated YAML shape is:

```yaml
modules:
  jmeter:
    path: /opt/surgepilot/apache-jmeter/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    force-ctg: false
  local:
    sequential: true
scenarios:
  scenario_01HZX3Y9M0E9W7Z6M5QK9S8P7A: {}  # produced by the P0-05 Scenario builder; abbreviated here
execution:
  - executor: jmeter
    scenario: scenario_01HZX3Y9M0E9W7Z6M5QK9S8P7A
    concurrency: 1
    iterations: 1
```

Rules:

1. Test Plan Debug executes all enabled Scenario items sequentially.
2. Test Plan Debug ignores saved Standard Run load settings.
3. Test Plan Debug emits `iterations: 1` and omits `hold-for`.
4. Test Plan Debug omits `throughput`, `steps`, `delay` and passfail reporting.
5. Test Plan Debug still validates referenced Scenarios, Env Group variables, Dependency Files and selected Load Node.

### 7.5 Load Settings Mapping

| SurgePilot field | Taurus field | P0 rule |
| --- | --- | --- |
| `concurrencyPerNode` | `concurrency` | Required positive integer for executable Scenario items. |
| `rampUpSeconds` | `ramp-up` | Emit only when `> 0`; format as Taurus time string such as `60s`. |
| `holdForSeconds` | `hold-for` | Emit when duration mode is used. Required for long-running Standard Runs unless `iterations` is used. |
| `iterations` | `iterations` | Mutually exclusive with `holdForSeconds` in P0. |
| `targetRps` | `throughput` | Optional. Allowed only when `holdForSeconds` is set and `rampUpSeconds > 0` or `holdForSeconds > 0`. |
| `steps` | `steps` | Optional for Standard Run only. Allowed only when `rampUpSeconds > 0`; requires `force-ctg: true` and preinstalled JMeter Custom Thread Groups plugin support. |
| `delaySeconds` | `delay` | Emit only when `> 0`; format as Taurus time string. Primarily useful for parallel start staggering; it is not a P0 scheduler. |

Validation rules:

1. An executable Scenario item must have exactly one termination mode: `holdForSeconds` or `iterations`.
2. `holdForSeconds` and `iterations` must not both be set.
3. `targetRps` and `steps` are omitted when null.
4. `targetRps` must not be used with Test Plan Debug.
5. `steps` must not be used with Test Plan Debug.
6. `steps` must not be used without ramp-up; Taurus requires `ramp-up` for stepping.
7. `steps` requires `modules.jmeter.force-ctg: true`; without `steps`, P0 YAML keeps `force-ctg: false`.
8. With `detect-plugins: false`, `steps` requires a selected Load Node whose runtime already has JMeter Custom Thread Groups plugin support.
9. In `runMode=sequential`, `delaySeconds` remains Taurus execution `delay`; UI copy must not present it as Schedule Run, queueing, or delayed retry.
10. API stores values as numbers and the builder converts to Taurus time strings.
11. API must reject negative, non-finite, non-integer where integer is required, and platform-threatening extreme values before Run creation.

### 7.6 SLA / Passfail Mapping

P0 SLA Rules map to Taurus passfail full-form criteria.

| SurgePilot field | Taurus field | P0 rule |
| --- | --- | --- |
| `subject` | `subject` | API allowed: `avg_rt`, `p90`, `p95`, `p99`, `fail`, `succ`, `hits`, `bytes`, or `rc<CODE>` pattern; builder emits Taurus `avg-rt` for `avg_rt`. |
| `label` | `label` | Optional. Empty or null means global aggregate. |
| `condition` | `condition` | API enum `gt`, `gte`, `lt`, `lte`, `eq`; builder emits `>`, `>=`, `<`, `<=`, `=`. |
| `threshold` | `threshold` | Builder emits Taurus-compatible value with unit. |
| `timeframeLogic` | `logic` | Optional `for` or `within`; P0 UI does not expose `over`. |
| `timeframeSeconds` | `timeframe` | Optional; when set, builder emits Taurus time string. |
| `action` | `stop` | `stop` emits `stop: true`; `continue` emits `stop: false`. |
| fixed | `fail` | Always `true` in P0. |

Subject rules:

1. `avg_rt`, `p90`, `p95` and `p99` use duration thresholds with `ms` or `s` units.
2. `fail` and `succ` use percentage thresholds in P0, matching the explicit Taurus passfail examples for these subjects.
3. `hits` uses `count` thresholds.
4. `bytes` uses `b`, `kb` or `mb` thresholds and emits `B`, `kB` or `MB`.
5. `rc<CODE>` supports concrete codes such as `rc500` and wildcard forms accepted by Taurus such as `rc4??` and `rc*`; P0 allows `percent` or `count` for this subject as shown by the local Taurus passfail response-code examples.
6. P0 does not expose `avg-lt`, `avg-ct`, `stdev-rt`, monitoring criteria, `non-failed` status or custom passfail messages.

Example mapping:

```json
{
  "subject": "p95",
  "label": null,
  "condition": "gt",
  "threshold": { "value": 500, "unit": "ms" },
  "timeframeLogic": "for",
  "timeframeSeconds": 10,
  "action": "continue"
}
```

emits:

```yaml
subject: p95
condition: ">"
threshold: 500ms
logic: for
timeframe: 10s
stop: false
fail: true
```

### 7.7 SLA Result Boundary

1. P0-06 owns storing SLA configuration and generating Taurus passfail criteria.
2. P0-06 does not own final Run Report parsing or SLA result presentation.
3. Standard Run Now with no enabled SLA Rules has `slaEvaluationMode=not_configured` in the snapshot.
4. Standard Run Now with enabled SLA Rules has `slaEvaluationMode=passfail` in the snapshot.
5. Test Plan Debug has `slaEvaluationMode=not_evaluated` in the snapshot.
6. P0-07 owns how final artifacts and passfail output become `slaResult=passed`, `failed` or `not_evaluated` in report APIs/UI.

---

## 8. Test Plan Product Model

### 8.1 Basic Information

A Test Plan has:

| Field | Required | Rules |
| --- | --- | --- |
| `name` | yes | 1 to 120 characters, trimmed, unique per active Workspace recommended but not required in P0. |
| `description` | no | Bounded plain text, max 1000 characters. API field may be named `description` even if UI label is Remark. |
| `tags` | no | Array of trimmed short strings, max 10 tags, each max 32 characters. |
| `revision` | yes | Integer optimistic revision, starts at 1 and increments on successful editable update. |

Rules:

1. Test Plan names and tags are user-facing and English UI labels are used in Web.
2. API does not require unique Test Plan name in P0 because list search and timestamps are enough for internal MVP.
3. Tags are metadata only; P0 does not implement tag management UI beyond inline editing.

### 8.2 Global Context

```json
{
  "envGroupId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "runMode": "sequential"
}
```

Rules:

1. `envGroupId` is optional for draft save.
2. If provided, `envGroupId` must reference a non-deleted Env Group in current Workspace.
3. Run creation validates that all required `${var}` tokens can be resolved by selected Env Group variables or Scenario extractors.
4. `runMode` is `sequential` or `parallel`; default is `sequential`.
5. `runMode=parallel` on a single node means multiple Taurus execution items run concurrently on the same selected Load Node.

### 8.3 Resource Configuration

```json
{
  "poolType": "private",
  "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
}
```

Rules:

1. `poolType` is `public` or `private`.
2. `selectedNodeId` is optional for draft save and required for Run creation.
3. When `poolType=public`, selected node must be a visible Public Load Node.
4. When `poolType=private`, selected node must be a current-Workspace Private Load Node.
5. At Run creation time, selected node must be `idle`, not archived, not disabled, not quarantined, not offline, not initializing, not busy, and must have no active lease.
6. If P0-04 force-kill cooldown is configured for selection safety, P0-06 Run creation must honor it.
7. Saved Test Plans may reference a node that later becomes unavailable; Run creation then returns a stable error and does not create a Run.
8. P0 does not implement node auto-replacement, queueing or delayed retry.

### 8.4 Scenario Orchestration Item

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
  "enabled": true,
  "order": 1,
  "loadSettings": {
    "concurrencyPerNode": 1,
    "rampUpSeconds": 0,
    "holdForSeconds": 60,
    "iterations": null,
    "targetRps": null,
    "steps": null,
    "delaySeconds": 0
  }
}
```

Rules:

1. Draft save may contain zero Scenario items.
2. Run creation requires at least one enabled Scenario item.
3. P0 max Scenario items per Test Plan is 20 by default.
4. Every Scenario item references a non-deleted Visual Scenario in the current Workspace.
5. Duplicate Scenario references are allowed when users intentionally run the same Scenario with different Load Settings.
6. `order` defines UI order and sequential execution order.
7. Disabled Scenario items are saved but excluded from Run Snapshot execution arrays and generated YAML execution items.
8. Item IDs are stable ULIDs generated by API or accepted from Web when validated as ULIDs.
9. Client-provided Scenario item IDs must be unique within a create or replacement PATCH payload; duplicates return `VALIDATION_ERROR` before DB insert.
10. Bulk Apply is not implemented; each item is edited independently.

### 8.5 Load Settings Defaults

Default Standard Run Load Settings for a new Scenario item:

```json
{
  "concurrencyPerNode": 1,
  "rampUpSeconds": 0,
  "holdForSeconds": 60,
  "iterations": null,
  "targetRps": null,
  "steps": null,
  "delaySeconds": 0
}
```

Rules:

1. Default settings are safe for internal MVP and can be executed on one initialized Load Node.
2. `concurrencyPerNode` represents the pressure on the single selected node in P0.
3. For `runMode=sequential`, expected single-node concurrency is the maximum `concurrencyPerNode` among enabled Scenario items.
4. For `runMode=parallel`, expected single-node concurrency is the sum of `concurrencyPerNode` among enabled Scenario items.
5. Test Plan Editor must display expected single-node concurrency.
6. P1 multi-node total concurrency is not displayed or computed in P0.

### 8.6 SLA Rule Model

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
  "enabled": true,
  "subject": "p95",
  "label": null,
  "condition": "gt",
  "threshold": { "value": 500, "unit": "ms" },
  "timeframeLogic": "for",
  "timeframeSeconds": 10,
  "action": "continue"
}
```

Rules:

1. SLA Rules are optional.
2. P0 supports up to 5 enabled SLA Rules.
3. Disabled SLA Rules may be saved but are not emitted to generated YAML.
4. Each enabled SLA Rule must be complete and valid.
5. `label` is an optional exact Taurus sampler label. Empty means whole-run evaluation and is omitted from the criterion; a non-empty value must match a generated request label for an enabled Scenario item.
6. P0 does not support nested boolean logic between SLA Rules; Taurus evaluates all emitted criteria.
7. P0 does not support custom passfail messages.
8. P0 does not support SLA based on live Monitoring metrics.
9. Client-provided SLA Rule IDs must be unique within a create or replacement PATCH payload; duplicates return `VALIDATION_ERROR` before DB insert.
10. SLA criteria are failure triggers. API and Web copy use `Fail when`; examples include `fail > 1%`, `avg_rt > 1000ms`, and `p95 > 2000ms`.

---

## 9. Data Model

### 9.1 `test_plans`

Purpose: Workspace-scoped reusable execution plan.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Workspace boundary. |
| `name` | `text` | yes | Trimmed name. |
| `description` | `text` | no | Bounded plain text. |
| `tags_json` | `jsonb` | yes | Array of strings, default `[]`. |
| `env_group_id` | `char(26)` | no | FK to Env Group in same Workspace. |
| `run_mode` | `text` | yes | `sequential` or `parallel`. |
| `pool_type` | `text` | no | `public` or `private`; nullable for draft. |
| `selected_node_id` | `char(26)` | no | FK to Load Node; nullable for draft. |
| `revision` | `integer` | yes | Starts at 1. |
| `created_by` | `char(26)` | yes | User ID. |
| `updated_by` | `char(26)` | yes | User ID. |
| `deleted_by` | `char(26)` | no | User ID. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |
| `deleted_at` | `timestamptz` | no | Soft delete marker. |

Constraints and indexes:

1. `id`, `workspace_id`, actor IDs, `env_group_id` and `selected_node_id` are ULID strings.
2. `run_mode in ('sequential', 'parallel')`.
3. `pool_type is null or pool_type in ('public', 'private')`.
4. `revision >= 1`.
5. Index `(workspace_id, deleted_at, updated_at desc, id desc)`.
6. Index `(workspace_id, lower(name))` for search.
7. Index `(workspace_id, env_group_id)` for Env Group reference check.
8. Index `(workspace_id, selected_node_id)` for diagnostics and list display.

Rules:

1. `workspace_id` is always set from resolved Workspace context.
2. List/detail/update/delete exclude `deleted_at is not null` by default.
3. Soft-deleted Test Plans cannot be Run sources.
4. Historical Run Snapshots remain immutable and are not changed when Test Plan is edited or deleted.

### 9.2 `test_plan_scenario_items`

Purpose: ordered references from Test Plan to Scenarios plus per-item Load Settings.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | Stable item ULID. |
| `workspace_id` | `char(26)` | yes | Denormalized for filtering and reference checks. |
| `test_plan_id` | `char(26)` | yes | FK to `test_plans.id`. |
| `scenario_id` | `char(26)` | yes | FK to `scenarios.id`. |
| `enabled` | `boolean` | yes | Default `true`. |
| `position` | `integer` | yes | Zero-based order. |
| `concurrency_per_node` | `integer` | yes | Positive for executable items. |
| `ramp_up_seconds` | `integer` | yes | Default `0`. |
| `hold_for_seconds` | `integer` | no | Termination mode. |
| `iterations` | `integer` | no | Termination mode. |
| `target_rps` | `numeric` | no | Optional throughput. |
| `steps` | `integer` | no | Optional stepping ramp. |
| `delay_seconds` | `integer` | yes | Default `0`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. Unique `(test_plan_id, id)`.
2. Unique `(test_plan_id, position)`.
3. Index `(workspace_id, scenario_id)` for Scenario delete protection.
4. `concurrency_per_node >= 1`.
5. `ramp_up_seconds >= 0`.
6. `delay_seconds >= 0`.
7. `hold_for_seconds is null or hold_for_seconds > 0`.
8. `iterations is null or iterations > 0`.
9. `target_rps is null or target_rps > 0`.
10. `steps is null or steps > 0`.
11. Exactly one of `hold_for_seconds` or `iterations` is non-null for enabled executable items.

Rules:

1. P0 PATCH replaces all Scenario item rows transactionally.
2. Scenario item rows are the authoritative Test Plan reference source for Scenario delete protection.
3. If a referenced Scenario is soft-deleted between save and Run, Run creation returns `RESOURCE_NOT_FOUND` or `TEST_PLAN_NOT_RUNNABLE` and does not create a Run.
4. Disabled items may keep incomplete run settings only if API explicitly excludes them from executable validation; P0 Web should still keep valid defaults.

### 9.3 `test_plan_sla_rules`

Purpose: ordered P0 SLA / Taurus passfail criteria.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | Stable rule ULID. |
| `workspace_id` | `char(26)` | yes | Denormalized for filtering. |
| `test_plan_id` | `char(26)` | yes | FK to `test_plans.id`. |
| `enabled` | `boolean` | yes | Default `true`. |
| `position` | `integer` | yes | Zero-based order. |
| `subject` | `text` | yes | P0 allowed subjects only. |
| `label` | `text` | no | Optional sampler label. |
| `condition` | `text` | yes | `gt`, `gte`, `lt`, `lte`, `eq`. |
| `threshold_value` | `numeric` | yes | Positive or zero depending on unit. |
| `threshold_unit` | `text` | yes | `ms`, `s`, `percent`, `count`, `b`, `kb`, `mb`. |
| `timeframe_logic` | `text` | no | `for` or `within`. |
| `timeframe_seconds` | `integer` | no | Optional positive duration. |
| `action` | `text` | yes | `continue` or `stop`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. Unique `(test_plan_id, id)`.
2. Unique `(test_plan_id, position)`.
3. Index `(workspace_id, test_plan_id)`.
4. `condition in ('gt', 'gte', 'lt', 'lte', 'eq')`.
5. `threshold_unit in ('ms', 's', 'percent', 'count', 'b', 'kb', 'mb')`.
6. `timeframe_logic is null or timeframe_logic in ('for', 'within')`.
7. `action in ('continue', 'stop')`.

Rules:

1. P0 PATCH replaces all SLA rows transactionally.
2. Enabled rules are validated against subject/unit compatibility.
3. Disabled rules may remain saved but are not emitted to passfail.
4. P0 does not store raw Taurus criteria strings as the source of truth.

### 9.4 Reference Checks Activated by P0-06

P0-06 activates real reference checks:

| Asset | Blocking P0-06 reference | Historical Snapshot behavior |
| --- | --- | --- |
| Env Group | Test Plan with `env_group_id`, including soft-deleted rows that still hold the FK | Historical Run Snapshots do not block delete. |
| Scenario | Non-deleted Test Plan Scenario item | Historical Run Snapshots do not block delete. |
| Load Node | Saved Test Plan selected node does not block disable/archive; Run creation revalidates availability. | Historical Run Snapshots do not block node changes. |
| Dependency File | No independent Test Plan reference. Scenario references from P0-05 continue to block deletion. | Historical Run Snapshots do not block delete. |

Rules:

1. Env Group delete returns existing `ENV_GROUP_IN_USE` when referenced by a Test Plan row that still holds the Env Group FK, including soft-deleted Test Plans.
2. Scenario delete returns `RESOURCE_IN_USE` when referenced by a non-deleted Test Plan.
3. Load Node unavailable state is handled at Run creation, not by preventing Test Plan save.
4. P0-06 must not introduce a `test_plan_dependency_file_refs` table unless a future P0 change adds independent Test Plan file selection.

### 9.5 Run Snapshot Extension

For `sourceType='test_plan'`, `run_snapshots.snapshot_json` extends the P0-04 shell with:

```json
{
  "schemaVersion": 1,
  "runType": "standard",
  "sourceType": "test_plan",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "sourceRevision": 4,
  "validityDefault": "valid",
  "slaEvaluationMode": "passfail",
  "testPlan": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "name": "Checkout Load Test",
    "description": "Checkout flow baseline",
    "tags": ["checkout"],
    "revision": 4,
    "runMode": "sequential"
  },
  "envGroup": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
    "name": "Staging",
    "variables": {
      "base_url": "https://staging.example.internal"
    }
  },
  "resourceRequest": {
    "mode": "manual",
    "poolType": "private",
    "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    "expectedConcurrencyPerNode": 10
  },
  "scenarioItems": [
    {
      "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
      "order": 0,
      "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
      "scenarioRevision": 3,
      "scenarioName": "Checkout flow",
      "loadSettings": {
        "concurrencyPerNode": 10,
        "rampUpSeconds": 60,
        "holdForSeconds": 300,
        "iterations": null,
        "targetRps": null,
        "steps": null,
        "delaySeconds": 0
      },
      "visualScenario": {}
    }
  ],
  "dependencyFiles": [],
  "slaRules": [],
  "generatedYaml": {
    "artifactRelativePath": "execution/generated.yml",
    "sha256": "..."
  }
}
```

Rules:

1. Snapshot captures only enabled Scenario items.
2. Snapshot captures the Scenario definition used for execution, not only Scenario IDs.
3. Snapshot captures Env Group variables as ordinary P0 values; P2 secret semantics are not implemented.
4. Snapshot excludes SSH credentials, Runner token, MinIO credentials, MinIO object keys, server absolute paths and raw private key material.
5. Snapshot may include script text from Scenario content because script text is part of executable Scenario definition; audit logs and general logs must not include script text.
6. `generatedYaml.artifactRelativePath` is a safe bundle-relative path, not a MinIO object key and not a user-visible preview route.
7. Snapshot hash is computed from canonical JSON after all validation and resolution.
8. Dedup uses snapshot hash and must not deduplicate across Workspace boundaries.

---

## 10. API Contract

All public APIs use:

1. `/api/v1` prefix;
2. cookie session auth;
3. `x-workspace-id` for Workspace-aware resources;
4. `x-csrf-token` for `POST`, `PATCH` and `DELETE`;
5. camelCase JSON fields;
6. generated OpenAPI as source of frontend client/types.

### 10.1 Shared Enums

```text
TestPlanRunMode = sequential | parallel
TestPlanPoolType = public | private
RunType = debug | standard
RunSourceType = protocol_smoke | debug_scenario | test_plan
SlaSubject = avg_rt | p90 | p95 | p99 | fail | succ | hits | bytes | rc<CODE>
SlaCondition = gt | gte | lt | lte | eq
SlaThresholdUnit = ms | s | percent | count | b | kb | mb
SlaTimeframeLogic = for | within
SlaAction = continue | stop
```

Rules:

1. `SlaSubject` values use API lower snake case; Web may render Taurus labels such as `avg-rt`.
2. `SlaSubject` for `rc<CODE>` is validated by pattern, not by finite enum list.
3. API response fields remain camelCase.
4. DB fields remain snake_case.
5. Web consumes enum unions through generated contracts.

### 10.2 `TestPlanSummary`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Checkout Load Test",
  "description": "Checkout flow baseline",
  "tags": ["checkout"],
  "runMode": "sequential",
  "envGroup": { "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7B", "name": "Staging" },
  "resource": {
    "poolType": "private",
    "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    "selectedNodeName": "staging-load-01",
    "selectedNodeStatus": "idle"
  },
  "scenarioItemCount": 2,
  "enabledScenarioItemCount": 2,
  "slaRuleCount": 1,
  "expectedConcurrencyPerNode": 10,
  "requiresHighConcurrencyConfirmation": false,
  "runnable": true,
  "notRunnableReasons": [],
  "revision": 4,
  "updatedAt": "2030-06-02T12:30:00.000Z",
  "updatedBy": { "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7U", "displayName": "Pat" }
}
```

Rules:

1. `runnable` is a server-computed convenience flag for UX only; Run creation remains authoritative.
2. `notRunnableReasons` contains stable safe codes, not localized copy.
3. Summary does not include full Scenario content, Env Group variable values or generated YAML.
4. Summary does not include MinIO object keys or Load Node credentials.

### 10.3 `TestPlanDetail`

`TestPlanDetail` includes all editable content:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Checkout Load Test",
  "description": "Checkout flow baseline",
  "tags": ["checkout"],
  "envGroupId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "runMode": "sequential",
  "resource": {
    "poolType": "private",
    "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
  },
  "scenarioItems": [],
  "slaRules": [],
  "runGuard": {
    "expectedConcurrencyPerNode": 10,
    "softConcurrencyPerNodeLimit": 1000,
    "hardConcurrencyPerNodeLimit": 10000,
    "requiresHighConcurrencyConfirmation": false
  },
  "runnable": true,
  "notRunnableReasons": [],
  "revision": 4,
  "createdAt": "2030-06-02T12:00:00.000Z",
  "updatedAt": "2030-06-02T12:30:00.000Z"
}
```

Rules:

1. Detail does not include generated YAML.
2. Detail does not include Env Group variable values.
3. Detail may include Scenario names and revisions for editor display.
4. Detail may include selected Load Node display metadata but never credentials.
5. `runGuard` values are computed from backend configuration and are the source for frontend warnings.

### 10.4 `GET /api/v1/test-plans`

Purpose: list current Workspace Test Plans.

Query params:

| Param | Required | Notes |
| --- | --- | --- |
| `page` | no | Offset pagination, default 1. |
| `pageSize` | no | Default 20, max 100. |
| `search` | no | Case-insensitive name search. |
| `tag` | no | Exact tag filter. |
| `sort` | no | P0 allowed: `-updatedAt`, `updatedAt`, `name`, `-name`. Default `-updatedAt`. |

Response: list envelope from `04` with `items: TestPlanSummary[]`.

Rules:

1. Filter by current Workspace.
2. Exclude soft-deleted rows.
3. Use offset pagination because Test Plan list is human-managed and expected to be small in P0.
4. Unknown sort returns `INVALID_QUERY_PARAMETER`.

### 10.5 `POST /api/v1/test-plans`

Purpose: create a Test Plan draft or complete saved plan.

Request:

```json
{
  "name": "Checkout Load Test",
  "description": "Checkout flow baseline",
  "tags": ["checkout"],
  "envGroupId": null,
  "runMode": "sequential",
  "resource": {
    "poolType": null,
    "selectedNodeId": null
  },
  "scenarioItems": [],
  "slaRules": []
}
```

Response:

- `201 Created`
- body: `TestPlanDetail`

Rules:

1. API sets `workspaceId`, `revision`, actor IDs and timestamps.
2. API may allow draft Test Plans with zero Scenario items, no Env Group and no selected node.
3. API validates any provided Env Group, Load Node and Scenario references in the current Workspace.
4. API returns `VALIDATION_ERROR` for invalid Load Settings or SLA Rules.
5. Create does not start a Run.

### 10.6 `GET /api/v1/test-plans/{testPlanId}`

Purpose: fetch editable Test Plan detail.

Rules:

1. Lookup by `(workspace_id, id, deleted_at is null)`.
2. Cross-Workspace IDs return `RESOURCE_NOT_FOUND`.
3. Response body is `TestPlanDetail`.

### 10.7 `PATCH /api/v1/test-plans/{testPlanId}`

Purpose: update editable Test Plan content.

Request includes full editable Test Plan content plus `expectedRevision`:

```json
{
  "expectedRevision": 4,
  "name": "Checkout Load Test",
  "description": "Checkout flow baseline",
  "tags": ["checkout", "baseline"],
  "envGroupId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "runMode": "sequential",
  "resource": {
    "poolType": "private",
    "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
  },
  "scenarioItems": [],
  "slaRules": []
}
```

Response:

- `200 OK`
- body: updated `TestPlanDetail`

Rules:

1. P0 PATCH behaves as replace-editable-content, not sparse nested JSON merge.
2. `expectedRevision` is required.
3. If `expectedRevision` does not match current `revision`, return `409 TEST_PLAN_REVISION_CONFLICT`.
4. On success, increment `revision` by 1.
5. Replace Scenario item rows and SLA Rule rows transactionally.
6. Active Runs using older snapshots are not modified.
7. PATCH does not start a Run.

### 10.8 `DELETE /api/v1/test-plans/{testPlanId}`

Purpose: soft-delete Test Plan.

Response:

- `204 No Content`

Rules:

1. Lookup by `(workspace_id, id, deleted_at is null)`.
2. If Test Plan has an active Run in `initializing`, `running` or `stopping`, return `RESOURCE_IN_USE`.
3. Historical Run Snapshots do not block deletion.
4. Soft delete sets `deleted_at`, `deleted_by` and updates `updated_at`.
5. Soft-deleted Test Plans cannot be Run sources.

### 10.9 `POST /api/v1/runs` for Test Plan Runs

Purpose: create Test Plan Debug or Standard Run Now.

Request:

```json
{
  "runType": "standard",
  "sourceType": "test_plan",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "expectedSourceRevision": 4,
  "confirmHighConcurrency": false
}
```

Response:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  "state": "initializing",
  "runType": "standard",
  "sourceType": "test_plan",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  "validity": "valid",
  "createdAt": "2030-06-02T12:40:00.000Z",
  "deduplicated": false
}
```

Status codes:

| Status | Meaning |
| --- | --- |
| `201 Created` | New Test Plan Run created. |
| `200 OK` | Short-window dedup hit; existing Run returned with `deduplicated: true`. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 FORBIDDEN` or `WORKSPACE_ACCESS_DENIED` | Actor cannot create Runs in current Workspace. |
| `404 RESOURCE_NOT_FOUND` | Test Plan or referenced asset is not visible in Workspace. |
| `409 TEST_PLAN_REVISION_CONFLICT` | `expectedSourceRevision` is stale. |
| `409 TEST_PLAN_NOT_RUNNABLE` | Test Plan is incomplete or contains unavailable references. |
| `409 LOAD_NODE_BUSY` | Selected node is already leased and request is not a dedup hit. |
| `409 LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED` | Expected concurrency exceeds soft limit and `confirmHighConcurrency` is not true. |
| `422 VALIDATION_ERROR` | Request shape, Load Settings, SLA Rules or variables are invalid. |

Rules:

1. P0-06 accepts only `runType=debug` or `runType=standard` with `sourceType=test_plan`.
2. P0-06 must continue rejecting `protocol_smoke` public product requests.
3. `sourceId` must be a non-deleted Test Plan in current Workspace.
4. `expectedSourceRevision` is required and must match current Test Plan `revision`.
5. Run request does not accept Env Group, Load Node, Load Settings or SLA overrides.
6. API validates Test Plan, Env Group, selected Load Node, Scenario references, variables, Dependency Files, Load Settings and SLA Rules before creating Run.
7. API enforces manual single Idle node selection.
8. If a Standard Run uses `steps`, API or startup preflight must verify the selected node satisfies the preinstalled JMeter Custom Thread Groups plugin prerequisite; otherwise the request returns `TEST_PLAN_NOT_RUNNABLE` or the Run fails safely before executing user load.
9. API atomically creates Run Snapshot, Run, node lease, Busy node state, dedup key and start request according to P0-04 transaction rules.
10. API does not execute SSH/SFTP or start Runner inside the DB transaction.
11. Standard Run Now uses saved Load Settings and enabled SLA Rules.
12. Test Plan Debug uses fixed low-risk profile and ignores saved Standard Run load settings for generated YAML.
13. On success, Web navigates to `/runs/:runId`.

### 10.10 High-Concurrency Confirmation Contract

When expected single-node concurrency exceeds soft limit:

1. API returns `409 LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED` unless `confirmHighConcurrency=true`.
2. Response includes safe details:

```json
{
  "code": "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED",
  "message": "Expected single-node concurrency exceeds the configured soft limit.",
  "details": [
    {
      "field": "scenarioItems",
      "code": "single_node_concurrency_soft_limit",
      "message": "Confirm that this run should start with high single-node concurrency.",
      "meta": {
        "expectedConcurrencyPerNode": 1200,
        "softLimit": 1000
      }
    }
  ],
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7S"
}
```

Rules:

1. Frontend must show explicit confirmation before retrying with `confirmHighConcurrency=true`.
2. Frontend duplicate-submit prevention is required, but API dedup remains authoritative.
3. Hard limits still reject even when `confirmHighConcurrency=true`.
4. `confirmHighConcurrency` is not persisted on the Test Plan.
5. Dedup key includes final validated snapshot hash; confirmation retry must not create duplicate Runs after the first successful create.

### 10.11 Error Code Registry

P0-06 adds or uses these error codes:

| Code | Status | Meaning |
| --- | --- | --- |
| `TEST_PLAN_REVISION_CONFLICT` | 409 | Test Plan was modified after the client loaded or saved it. |
| `TEST_PLAN_NOT_RUNNABLE` | 409 | Saved Test Plan is incomplete or references unavailable resources. |
| `LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED` | 409 | Run exceeds configured soft concurrency limit and needs explicit user confirmation. |
| `LOAD_NODE_BUSY` | 409 | Selected node is already leased by another Run. |
| `RESOURCE_IN_USE` | 409 | Test Plan or referenced asset cannot be deleted while in use. |
| `VALIDATION_ERROR` | 422 | Request shape, Load Settings, SLA, variables or references are invalid. |

Rules:

1. Register P0-06-specific codes before implementation returns them.
2. Use existing `RESOURCE_NOT_FOUND` for cross-Workspace Test Plan, Env Group, Scenario, Dependency File and Load Node IDs.
3. Use existing `ENV_GROUP_IN_USE` when Env Group deletion is blocked by Test Plan references.
4. Error messages and details must not include Env Group values, Step body, script text, MinIO object keys, server paths, SSH credentials or runner tokens.

---

## 11. Execution Builder Contract

### 11.1 Inputs

Execution builder input for P0-06 is a fully validated immutable build context:

1. actor ID and Workspace ID;
2. Run ID;
3. run type: `standard` or `debug`;
4. Test Plan detail with matched revision;
5. selected Env Group values if present;
6. selected Load Node safe metadata;
7. enabled Scenario items ordered by `position`;
8. full Scenario definitions and revisions from P0-05;
9. Dependency File metadata and safe runner-local bundle paths;
10. enabled SLA Rules for Standard Run Now.

Rules:

1. Builder never queries database directly if service already constructed a validated context.
2. Builder never receives or emits SSH credentials, Runner token, MinIO credentials or MinIO object keys.
3. Builder output is deterministic for canonical equivalent input.
4. Builder output is stored as internal execution bundle content and may be registered as an artifact through P0-04/P0-07 boundaries.

### 11.2 Validation Before Bundle Generation

API service must validate:

1. Test Plan is current Workspace, non-deleted and revision matches request.
2. At least one enabled Scenario item exists.
3. Enabled Scenario item count is within configured limit.
4. Every enabled Scenario is current Workspace, non-deleted and `scenarioType=visual`.
5. Env Group, if required by variables or selected explicitly, is current Workspace and non-deleted.
6. All `${var}` tokens resolve through Env Group variables or earlier Scenario extractors according to P0-05 rules.
7. Dependency Files referenced by Scenarios are current Workspace and not deleted.
8. Selected Load Node is visible, matches Pool Type and is selectable under P0-04 / P0-03 rules.
9. Expected single-node concurrency is within hard limits and confirmed if above soft limit.
10. Standard Run items using `steps` have JMeter Custom Thread Groups plugin support available on the selected node or fail before user load starts.
11. SLA Rules are valid and map to Taurus passfail fields.
12. No P1/P2 resource fields appear in request payload.

### 11.3 Bundle Contents

P0-06 execution bundle includes at least:

```text
run-bundle/
  manifest.json
  generated.yml
  scenarios/
    <scenario-alias>.json
  files/
    <safe-dependency-file-name>
```

Rules:

1. Bundle paths are safe relative paths.
2. Bundle paths must not contain `..`, absolute path prefixes, backslashes, control characters or empty segments.
3. `generated.yml` is internal only.
4. `manifest.json` may include Run ID, source type, Test Plan ID, revisions and safe bundle paths.
5. `manifest.json` must not include secrets, MinIO object keys or server absolute paths.
6. Dependency Files are copied or staged through API-owned storage access; Runner never receives MinIO credentials.

### 11.4 Runner Boundary

1. API/api-worker prepares bundle and remote start request.
2. Runner executes the bundle and sends callbacks through the P0-04 runner protocol.
3. Runner must not import `apps/api` code.
4. Runner must not access PostgreSQL or MinIO directly.
5. Runner callback schema remains `packages/contracts/runner/runner-callback.schema.json`.
6. P0-06 must not add internal runner endpoints to public OpenAPI or Web generated client.

---

## 12. Load Guard and Runtime Configuration

P0-06 uses backend-owned configuration for Run safety.

| Setting | Default | Purpose |
| --- | --- | --- |
| `SURGEPILOT_MAX_SCENARIO_ITEMS_PER_TEST_PLAN` | `20` | Max Scenario items in one Test Plan. |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT` | `1000` | Soft warning threshold requiring confirmation. |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT` | `10000` | Hard rejection threshold. |
| `SURGEPILOT_MAX_RUN_DURATION_SECONDS` | `86400` | Max `holdForSeconds` per Scenario item. |
| `SURGEPILOT_MAX_RAMP_UP_SECONDS` | `86400` | Max `rampUpSeconds` per Scenario item. |
| `SURGEPILOT_MAX_DELAY_SECONDS` | `86400` | Max `delaySeconds` per Scenario item. |
| `SURGEPILOT_MAX_ITERATIONS` | `1000000` | Max iterations per Scenario item. |
| `SURGEPILOT_MAX_TARGET_RPS` | `100000` | Max target RPS per Scenario item. |
| `SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN` | `5` | Max enabled SLA Rules. |

Rules:

1. API is authoritative for all guard values.
2. Web must use `runGuard` values returned by API for warning copy and confirmation prompts.
3. Per-item hard limits reject save with `VALIDATION_ERROR`; aggregate expected-concurrency hard limits mark the saved Test Plan as not runnable and reject Standard Run creation with `VALIDATION_ERROR`.
4. Soft limit only requires explicit confirmation at Run creation.
5. Soft and hard limits must not be hard-coded in multiple frontend locations.
6. Configuration values are not editable through P0 UI.
7. Setup Status may show whether guard configuration is present, but not as an editable System Settings page.

---

## 13. Frontend Contract

### 13.1 Routes and Navigation

P0-06 implements:

| Page | Route | Layout |
| --- | --- | --- |
| Test Plan List | `/test-plans` | `AppLayout` |
| Test Plan Editor | `/test-plans/:planId` | `AppLayout` |

Rules:

1. Routes are feature-owned under `apps/web/src/features/test-plans/routes.tsx` or equivalent established structure.
2. Root router only aggregates route objects.
3. Business data uses TanStack Query, not React Router loaders.
4. Web consumes generated types/client through `@surgepilot/contracts` only.
5. No P1/P2 clickable routes are added.
6. Run success navigates to `/runs/:runId`; if P0-07 is not implemented yet, route handoff may show a minimal Run-owned handoff view and must not expose P1/P2 capability.

### 13.2 Test Plan List Page

Page capabilities:

1. list Test Plans with name and tags, run mode, scenario item count, expected concurrency, and updated time; Env Group, selected node, and updated by are not list columns;
2. search by name;
3. sort by updated time or name;
4. create Test Plan;
5. open Test Plan Editor;
6. delete Test Plan with confirmation;
7. Quick Run only when `runnable=true` and no high-concurrency confirmation is required;
8. show empty, loading, error and permission states.

Rules:

1. Create Test Plan uses a small form for name, description and optional tags.
2. On successful create, navigate to `/test-plans/:planId`.
3. Delete confirmation states that historical Run Reports keep snapshots.
4. Delete blocked by active Runs shows stable copy based on `RESOURCE_IN_USE`.
5. Quick Run must call the same `POST /api/v1/runs` contract as Editor Run Now.
6. Quick Run must not bypass revision, node, guard or dedup validation.
7. If a plan is not runnable, Quick Run opens the Editor instead of creating a Run.

### 13.3 Test Plan Editor Page

Page sections:

1. Basic Information: name, description, tags, revision and save status;
2. Global Context: Env Group selector and Run Mode selector;
3. Resource Configuration: Pool Type, one selected Idle Load Node and expected single-node concurrency;
4. Scenario Orchestration: add/remove/reorder Scenario items;
5. per-item Load Settings editor;
6. SLA Rules editor;
7. Actions: Save, Debug, Run Now.

Rules:

1. UI labels use product terms Test Plan, Scenario Orchestration, Load Settings, SLA Rules, Debug and Run Now.
2. User-facing copy is English only.
3. Unsaved changes must be visible.
4. Navigating away with unsaved changes prompts the user.
5. Run actions for saved plans use backend runnable state; Debug may remain available for Standard-only hard-limit reasons because Debug uses the fixed low-risk profile.
6. If there are unsaved changes, primary actions are `Save and Debug` and `Save and Run Now`; they may be enabled after minimum local prerequisites are selected, but must re-check the saved response before creating a Run.
7. Frontend must not execute a Run against local unsaved draft content or a saved response that is not eligible for the requested Run type.
8. Frontend must not build Taurus YAML.
9. Frontend must not call internal Runner endpoints.
10. Frontend must not display Generated YAML Preview in P0.

### 13.4 Scenario Orchestration Editor

Minimum controls:

1. add Scenario from current Workspace Scenario selector;
2. show Scenario name, revision, enabled Step count and last updated time;
3. remove item;
4. reorder item;
5. edit per-item Load Settings;
6. show item-level validation errors.

Rules:

1. Duplicate Scenario references are allowed.
2. P0 UI uses an add-means-enabled model: a visible Scenario item is saved as enabled and participates in Run Now; users remove the item when it should not run.
3. The backend `enabled` field remains in the contract for execution filtering and future compatibility, but P0 UI does not expose an enable/disable control.
4. Reorder preserves item IDs.
5. Removing an item removes it from the saved Test Plan after save; historical Run Snapshots are unaffected.
6. Bulk Apply is not implemented in P0.
7. Selector must exclude soft-deleted Scenarios.
8. Selector must not include API Catalog or import actions.

### 13.5 Load Settings Editor

Minimum controls per Scenario item:

1. Concurrency / Node;
2. Ramp-up;
3. Hold-for or Iterations mode;
4. Throughput / target RPS optional;
5. Steps optional;
6. Delay optional.

Rules:

1. Use simple numeric inputs and unit labels; do not introduce a reusable load profile builder.
2. Frontend validates obvious input errors for UX, but API validation remains authoritative.
3. If `steps` is set and `rampUpSeconds=0`, show field-level error.
4. If `targetRps` is set without duration-compatible settings, show field-level error.
5. Expected single-node concurrency updates from saved or editable values for user guidance.
6. High-concurrency confirmation copy uses API `runGuard` when available; final enforcement happens during Run creation.

### 13.6 SLA Rule Editor

Minimum controls:

1. subject select;
2. optional label input;
3. condition select;
4. threshold value and unit;
5. optional timeframe logic and duration;
6. action select: Continue or Stop;
7. remove rule.

Rules:

1. P0 UI supports at most 5 enabled SLA Rules.
2. P0 UI uses an add-means-enabled model: a visible SLA Rule is saved as enabled and participates in Standard Run Now; users remove the rule when it should not be evaluated.
3. The backend `enabled` field remains in the contract for execution filtering and future compatibility, but P0 UI does not expose an enable/disable control.
4. Subject list is restricted to P0 allowed subjects.
5. `rc<CODE>` uses a text input with validation for `rc500`, `rc4??`, `rc*` and equivalent Taurus-supported wildcard patterns; blank response-code pattern input is normalized to wildcard `rc*`.
6. Threshold unit options depend on subject.
7. Frontend must not expose monitoring-based criteria, `over` logic, `non-failed` status or custom messages.

### 13.7 Run Actions UX

Run action behavior:

1. `Debug` creates `runType=debug`, `sourceType=test_plan`.
2. `Run Now` creates `runType=standard`, `sourceType=test_plan`.
3. Both actions require saved revision.
4. Both actions show submit state and duplicate-click protection.
5. On `201` or dedup `200`, navigate to `/runs/:runId`.
6. On `TEST_PLAN_REVISION_CONFLICT`, show reload prompt.
7. On `LOAD_NODE_BUSY`, refresh Load Node options.
8. On `TEST_PLAN_NOT_RUNNABLE` or `VALIDATION_ERROR`, keep user on the page and show section errors where possible.
9. On `LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED`, show explicit confirmation and retry with `confirmHighConcurrency=true` only after user confirms.

---

## 14. Security, Permission, and Workspace Rules

### 14.1 Authentication and CSRF

1. All Test Plan public APIs require session auth.
2. `POST`, `PATCH` and `DELETE` require `x-csrf-token`.
3. `POST /api/v1/runs` for Test Plan Runs requires session auth and CSRF.
4. Web must use generated client middleware to send session, Workspace header and CSRF token.

### 14.2 Workspace Enforcement

1. Test Plan list, detail, create, update, delete and Run creation are Workspace-aware.
2. API resolves Workspace from `x-workspace-id` or P0 default Workspace fallback.
3. All Test Plan rows, Scenario item rows and SLA rows carry `workspace_id` or are reachable only through a Workspace-filtered parent.
4. Cross-Workspace Test Plan, Env Group, Scenario, Dependency File and Private Load Node IDs return `RESOURCE_NOT_FOUND` unless `04` / `06` require a stricter error.
5. Public Load Node selection still requires current Workspace Run creation authorization.

### 14.3 Authorization

1. Admin and User may manage Test Plans in the current Workspace.
2. Admin and User may create Test Plan Runs in the current Workspace.
3. Backend permissions are authoritative; frontend hiding buttons is not sufficient.
4. Public Load Node management remains Admin-only, but using an eligible Public Load Node for a Run is allowed according to Run creation rules.
5. Private Load Node selected for a Test Plan must belong to the current Workspace.

### 14.4 Sensitive Data Rules

1. Test Plan APIs never return Load Node credentials.
2. Test Plan APIs never return MinIO credentials or object keys.
3. Test Plan APIs never return Runner token.
4. Snapshot excludes infrastructure secrets and storage internals.
5. Env Group P0 variables are ordinary values and may be snapshotted for reproducibility, but they must not be written to audit details or general logs.
6. Scenario script text may be part of the execution snapshot, but must not be written to audit details, validation error details or general application logs.

### 14.5 Path Safety

1. P0-06 relies on P0-02/P0-05 Dependency File safe metadata and P0-04/P0-07 artifact safe relative path rules.
2. Generated bundle paths must be bundle-relative and normalized.
3. API must reject absolute paths, `..`, `.`, empty segments, backslashes, drive letters, colon and control characters in generated bundle-relative paths.
4. Web never receives server absolute paths or MinIO object keys.

### 14.6 Audit Events

P0-06 follows `06` audit principles: ordinary Test Plan CRUD does not require full P0 audit coverage.

P0-06 activates these execution-control audit events:

| Event | Trigger | Safe details |
| --- | --- | --- |
| `run.debug_requested` | Test Plan Debug requested | Include actor, run ID, Test Plan ID, revision, selected node ID, Workspace ID and request ID. |
| `run.standard_requested` | Standard Run Now requested | Include actor, run ID, Test Plan ID, revision, selected node ID, Workspace ID, expected concurrency and request ID. |

Rules:

1. Audit details must not include Env values, Step body, script text, credentials, tokens, MinIO object keys or server paths.
2. The P0 audit event registry includes `run.standard_requested` for P0-06 Run Now.
3. P0-06 does not implement audit log UI, audit export or audit retention cleanup.

---

## 15. Contract Rules

P0-06 contract rules:

1. FastAPI routes and Pydantic schemas are the OpenAPI source of truth.
2. `packages/contracts/openapi/api.openapi.json` is generated and must not be handwritten.
3. Web imports generated client/types through `@surgepilot/contracts` only.
4. Internal Runner endpoints remain excluded from public OpenAPI/Web client.
5. API field names are camelCase; DB column names are snake_case.
6. Error codes must be present in the contract before API returns them.
7. Test Plan Web consumers must not invent request or response shapes outside generated contracts.
8. Generated YAML, Runner callbacks and artifact internals are not public Web contracts.

---

## 16. Cross-Slice Handoff Contracts

### 16.1 P0-05 Handoff

P0-06 must reuse:

1. Visual Scenario schema and validation rules;
2. Scenario revision and delete protection service boundary;
3. Scenario Dependency File refs;
4. P0-05 Taurus requests-scenario builder;
5. Scenario variable resolution rules;
6. Run creation dedup table/service if implemented by P0-05.

Rules:

1. P0-06 must not fork or duplicate Scenario-to-Taurus mapping.
2. P0-06 must not modify saved Scenario content during Test Plan Run creation.
3. P0-06 snapshot captures Scenario content as of Run creation.

### 16.2 P0-04 Handoff

P0-06 calls P0-04 Run creation service with already-validated execution input.

Rules:

1. Exactly one selected Load Node is passed.
2. Run creation service owns atomic Run, Snapshot, node lease, Busy node state and start request creation.
3. P0-06 must not execute SSH/SFTP inside the DB transaction.
4. P0-06 must not bypass Stop, heartbeat timeout, late callback or node lease rules.
5. P0-06 keeps `SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS=false` for production product APIs.

### 16.3 P0-07 Handoff

P0-07 receives:

1. `sourceType=test_plan` Runs;
2. Test Plan Snapshot payload;
3. `validity` defaults for Test Plan Debug and Run Now;
4. `slaEvaluationMode` in snapshot;
5. generated YAML artifact metadata when available;
6. Run artifacts uploaded through Runner protocol;
7. Taurus final-stats CSV produced through `final-stats` `dump-csv` and uploaded as `final_stats_csv` when available.

P0-07 owns:

1. Run Report detail APIs;
2. KPI summary from `final_stats_csv`;
3. SLA result presentation and final interpretation;
4. artifacts list/download/preview;
5. Valid / Invalid mutation UI;
6. Run List / Report polling behavior;
7. the P0 decision that failed requests plugin preview is deferred to P1.

---

## 17. Tests

### 17.1 API Unit Tests

Required:

1. Test Plan create defaults `revision=1`, `runMode=sequential` and safe load defaults.
2. PATCH requires matching `expectedRevision` and increments revision.
3. PATCH replaces Scenario item rows transactionally.
4. PATCH replaces SLA rows transactionally.
5. Env Group reference check reports in use for Test Plans that still hold an Env Group FK, including soft-deleted rows.
6. Scenario reference check reports in use for non-deleted Test Plans.
7. Expected concurrency calculation uses max for sequential and sum for parallel.
8. Load Settings validation rejects negative values, both hold-for and iterations, missing termination mode, steps without ramp-up, and target RPS without compatible duration.
9. Hard concurrency limit rejects even with confirmation.
10. Soft concurrency limit requires confirmation.
11. SLA subject/unit compatibility is enforced.
12. SLA condition enum maps to Taurus symbols.
13. SLA threshold units emit Taurus-compatible values, including bare numeric count thresholds.
14. Duplicate client-provided Scenario item IDs and SLA Rule IDs return `VALIDATION_ERROR` for create and PATCH before DB insert.
15. Standard Run builder emits multiple execution items, sets `force-ctg` from emitted `steps`, and emits passfail reporting when SLA Rules are enabled.
16. Debug builder emits sequential low-risk execution and no passfail reporting.
17. Snapshot builder excludes credentials, MinIO object keys and server paths.
18. Dedup key hash is stable for canonical equivalent input.
19. Dedup does not reuse Runs across Workspace boundaries.

### 17.2 API Integration Tests

Required:

1. Create Test Plan returns `201` and `revision=1`.
2. List Test Plans is Workspace-isolated.
3. Get Test Plan cross-Workspace returns `RESOURCE_NOT_FOUND`.
4. PATCH with stale revision returns `TEST_PLAN_REVISION_CONFLICT`.
5. DELETE soft-deletes Test Plan and removes it from list.
6. DELETE active-running Test Plan returns `RESOURCE_IN_USE`.
7. Env Group delete is blocked when referenced by Test Plan.
8. Scenario delete is blocked when referenced by Test Plan.
9. Run Now with valid Test Plan creates Run `initializing` with `runType=standard`, `sourceType=test_plan`.
10. Test Plan Debug creates Run `initializing` with `runType=debug`, `sourceType=test_plan`.
11. Run Now creates Run Snapshot with Test Plan, Scenario items, Env Group, Dependency Files, Load Settings, SLA and Resource Request.
12. Run Now marks selected Load Node Busy through P0-04 lease flow.
13. Duplicate Run Now request within 30 seconds returns existing Run with `deduplicated=true`.
14. Duplicate Run Now request does not create a second node lease.
15. Run Now with busy node and no dedup hit returns `LOAD_NODE_BUSY`.
16. Run Now stale Test Plan revision returns `TEST_PLAN_REVISION_CONFLICT`.
17. Run Now incomplete Test Plan returns `TEST_PLAN_NOT_RUNNABLE`.
18. Run Now soft-limit breach without confirmation returns `LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED`.
19. Run Now soft-limit breach with confirmation creates Run if hard limits pass.
20. Test Plan Debug uses fixed low-risk profile in snapshot/build output.
21. Referenced Scenario or Env Group from another Workspace returns `RESOURCE_NOT_FOUND`.
22. Missing variables return `VALIDATION_ERROR` with field details.

### 17.3 Contract Tests

Required:

1. Test Plan endpoints appear in exported OpenAPI under `/v1/test-plans`.
2. Public `POST /v1/runs` supports P0-06 `sourceType=test_plan` shapes.
3. API fields are camelCase.
4. `TEST_PLAN_REVISION_CONFLICT`, `TEST_PLAN_NOT_RUNNABLE` and `LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED` appear in documented error responses.
5. Generated Web client exposes Test Plan CRUD and public Test Plan Run create.
6. Generated Web client does not expose `/api/internal/v1/runner/...`.
7. OpenAPI stale check fails when contracts are not regenerated after schema changes.

### 17.4 Web Tests

Required:

1. Test Plan List renders loading, empty, error and populated states.
2. Create Test Plan submits through generated client and navigates to detail.
3. Test Plan Editor loads detail via TanStack Query.
4. Basic Information save sends `expectedRevision` and handles success.
5. Stale revision error shows reload prompt.
6. Unsaved navigation prompts user.
7. Scenario Orchestration add/remove/reorder preserves item IDs and saves visible items as enabled.
8. Load Settings validates hold-for vs iterations and steps/ramp-up relationship.
9. Expected single-node concurrency displays max for sequential and sum for parallel.
10. SLA Rule editor restricts subject/unit/action options.
11. Run Now requires saved runnable plan.
12. Save and Run Now saves first, then creates Run with returned revision.
13. Debug creates `runType=debug` and Run Now creates `runType=standard`.
14. High-concurrency 409 shows confirmation and retries with `confirmHighConcurrency=true` only after confirmation.
15. `LOAD_NODE_BUSY` refreshes node options.
16. Run success navigates to `/runs/:runId`.
17. Web does not contain internal Runner endpoint strings.
18. Web does not render Schedule Run, Auto allocation, multi-node selection, Bulk Apply or Generated YAML Preview.

### 17.5 Runner / Smoke Tests

Required fake-runner smoke:

1. Test Plan Run Now happy path reaches `finished` through P0-04 callback flow.
2. Test Plan Run Now failed path reaches `failed`.
3. Stop from Test Plan Run Now reaches `aborted` and releases node safely.
4. Test Plan Debug happy path reaches `finished` with low-risk profile.
5. Artifact upload from Test Plan Run creates metadata without object key exposure.

Real or near-real SSH/Taurus smoke belongs to `make verify-e2e` when an SSH-capable Load Node environment is provided. The P0-06 engineering smoke is implemented by `scripts/verify_p0_06_ssh_taurus_smoke.py` and Make targets `verify-p0-06-runner-ssh` / `verify-p0-06-runner-ssh-fast`; it creates a Scenario against `GET /api/healthz`, runs a 10-second Standard Test Plan through the SSH load-node container, verifies terminal cleanup, lease release and MinIO artifact objects, then runs a 30-second Stop convergence check.

---

## 18. Verification Commands

Implementation must run:

```bash
make generate-contracts
make verify
```

When real SSH/Taurus environment is available, run:

```bash
make verify-e2e
```

Targeted commands during implementation may include:

```bash
uv run --all-packages pytest apps/api/tests -k "test_plan or run_now"
uv run --all-packages pytest apps/runner/tests -k "callback or artifact or fake_runner"
pnpm --filter @surgepilot/web test -- test-plans
pnpm --filter @surgepilot/web typecheck
make contracts-stale-check
make verify-p0-06-runner-ssh-fast
```

Rules:

1. `make verify` remains the default completion gate.
2. If `make verify-e2e` or `make verify-p0-06-runner-ssh-fast` cannot run due to missing SSH/Taurus environment or missing local images, final response must state the environment gap.
3. `verify-p0-06-runner-ssh-fast` rebuilds API images but reuses `docker-ssh-load-node:latest`; `verify-p0-06-runner-ssh` rebuilds both API and SSH load-node images before running the same acceptance flow.
4. Documentation-only changes may run a lighter document validation and git diff check, but implementation PRs must run the full gates above.

---

## 19. Done When

P0-06 is done when:

1. Test Plan CRUD API is implemented with Workspace, auth, CSRF and permission checks.
2. Test Plan Pydantic schemas export correct OpenAPI.
3. Web uses generated Test Plan and Run client/types through `@surgepilot/contracts`.
4. Test Plan revision conflict is enforced on save and Run creation.
5. Scenario item references are validated, stored and used for Scenario delete protection.
6. Env Group reference is used for Env Group delete protection.
7. Load Settings validation and input guards are enforced by backend.
8. High-concurrency soft warning requires explicit confirmation before Run creation.
9. Test Plan Debug uses `POST /api/v1/runs` with `runType=debug` and `sourceType=test_plan`.
10. Run Now uses `POST /api/v1/runs` with `runType=standard` and `sourceType=test_plan`.
11. Run creation dedup returns existing Run within short window and does not create duplicate leases.
12. Run creation uses manual single Idle node selection only.
13. Run Snapshot contains Test Plan, Scenario, Env Group, Dependency File, Load Settings, SLA and Resource Request data without sensitive infrastructure values.
14. Taurus YAML generation follows §7 and §11.
15. Generated YAML remains internal and is not editable or previewed in P0 UI.
16. Test Plan List and Editor routes follow `08` routing and data-fetching rules.
17. Debug / Run Now success navigates to `/runs/:runId`.
18. API, contract, web and smoke tests from §17 pass.
19. `make generate-contracts` and `make verify` pass for implementation PRs.
20. No P1/P2 user-visible capability is introduced.

---

## 20. Review Checklist

### 20.1 Scope

- [ ] Does the change stay within Test Plan and Test Plan Run creation?
- [ ] Does it avoid API Catalog, cURL import and OpenAPI import?
- [ ] Does it avoid Clone, Bulk Apply, Schedule Run and Generated YAML Preview?
- [ ] Does it avoid Auto allocation, Node Count, Selected Nodes array and multi-node execution?
- [ ] Does it avoid Monitoring, Grafana and InfluxDB?

### 20.2 Contracts

- [ ] Are API schemas source of truth for OpenAPI?
- [ ] Are generated contracts refreshed?
- [ ] Does Web use `@surgepilot/contracts` only?
- [ ] Are API fields camelCase?
- [ ] Are enum values lower snake case where applicable?
- [ ] Are error codes registered before implementation returns them?

### 20.3 Test Plan and Taurus

- [ ] Does each Test Plan field map to product data or an official Taurus field?
- [ ] Does Standard Run Now emit valid Taurus execution items?
- [ ] Does sequential mode use `modules.local.sequential: true` only?
- [ ] Does parallel mode rely on Taurus default parallel execution?
- [ ] Does builder avoid `modules.local.capacity` in P0?
- [ ] Does builder set `force-ctg: true` only when Standard Run emits `steps`, and otherwise keep `force-ctg: false`?
- [ ] Does Test Plan Debug force low-risk settings and omit passfail?
- [ ] Do SLA Rules emit valid Taurus passfail full-form criteria?
- [ ] Is generated YAML internal only?

### 20.4 Run and Node Safety

- [ ] Does Run creation use P0-04 Run state machine service?
- [ ] Does Run creation atomically acquire a single node lease?
- [ ] Does dedup avoid duplicate leases and duplicate starts?
- [ ] Does selected node validation enforce Idle, visibility, Pool Type and Workspace boundaries?
- [ ] Does Stop remain P0-04-owned and idempotent?
- [ ] Are soft and hard load guards enforced by backend?

### 20.5 Security

- [ ] Are all public writes protected by CSRF?
- [ ] Are all resources filtered by Workspace?
- [ ] Are Env Group, Scenario and Load Node references current-Workspace safe?
- [ ] Are MinIO object keys never returned to Web?
- [ ] Are SSH credentials, runner tokens and storage credentials excluded from snapshots and logs?
- [ ] Are script text and Env values excluded from audit details and general logs?

### 20.6 Frontend

- [ ] Are routes feature-owned and lazy-loaded?
- [ ] Does business data use TanStack Query?
- [ ] Does Save and Run save first and use returned revision?
- [ ] Does Run require one Idle Load Node?
- [ ] Does high-concurrency confirmation require explicit user action?
- [ ] Does Run success navigate to `/runs/:runId`?
- [ ] Does UI copy remain English only and centralized?
- [ ] Are Bulk Apply, Schedule Run, Auto allocation, multi-node and Generated YAML Preview absent?

### 20.7 Verification

- [ ] `make generate-contracts` was run after API schema changes.
- [ ] `make verify` passed.
- [ ] `make verify-e2e` was run when real SSH/Taurus environment was available.
- [ ] Final response lists changed files, verification commands/results and remaining risks.
