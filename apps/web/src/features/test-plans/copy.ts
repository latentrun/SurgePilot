export const testPlanCopy = {
  title: "Test Plans",
  subtitle:
    "Orchestrate saved Scenarios, load settings, resources, and SLAs for repeatable runs.",
  emptyTitle: "No test plans yet",
  emptyDescription:
    "Create a Test Plan to combine Scenarios with load settings and a Load Node.",
  createButton: "Create Test Plan",
  createTitle: "Create Test Plan",
  rename: "Rename Test Plan",
  renameInputLabel: "Test Plan title",
  delete: "Delete",
  deleteTitle: "Delete Test Plan",
  deleteBody:
    "This Test Plan will be hidden from active lists. Historical Run Reports keep their saved snapshots.",
  resourceInUse:
    "Test Plan cannot be deleted while it is referenced by active execution state or visible dependent resources.",
  highConcurrencyTitle: "Confirm high concurrency",
  highConcurrencyBody:
    "This run exceeds the configured single-node soft limit. Confirm that the selected node is prepared for this load.",
  highConcurrencyMeta: (value: number, softLimit: number) =>
    `Expected: ${value} / Soft limit: ${softLimit}`,
  highConcurrencyFromList:
    "Open the editor to confirm high concurrency before running.",
  unsavedPrompt: "You have unsaved Test Plan changes. Leave without saving?",
  staleRevision: "Test Plan changed elsewhere. Reload and try again.",
  notRunnable: "Complete the required sections before starting a Run.",
  loadingList: "Loading test plans…",
  loadingDetail: "Loading Test Plan…",
  listLoadError: "Unable to load Test Plans.",
  detailLoadError: "Unable to load Test Plan.",
  actionFailed: "Action failed. Refresh and try again.",
  nodeBusy: "Selected Load Node is no longer idle. Refresh resources and try again.",
  validationError:
    "Review the highlighted Test Plan settings before running.",
  backToList: "← Test Plans",
  untitled: "Untitled Test Plan",
  saved: "Saved",
  unsaved: "Unsaved changes",
  save: "Save",
  saving: "Saving...",
  debug: "Debug",
  saveAndDebug: "Save and Debug",
  runNow: "Run Now",
  saveAndRunNow: "Save and Run Now",
  startingDebug: "Starting Debug Run...",
  startingRun: "Starting Run...",
  cancel: "Cancel",
  create: "Create",
  open: "Open",
  quickRun: "Quick Run",
  confirmAndRun: "Confirm and run",
  basicInfo: "Basic Information",
  globalContext: "Global Context",
  resourceConfiguration: "Resource Configuration",
  scenarioOrchestration: "Scenario Orchestration",
  scenarioOrchestrationHelp:
    "Add saved Visual Scenarios and tune each item independently.",
  noScenarioItems: "No Scenario items yet.",
  addScenario: "Add Scenario",
  slaRules: "SLA Rules",
  slaRulesHelp:
    "Rules define failure conditions for Standard Runs. Examples: fail > 1%, avg_rt > 1000ms, and p95 > 2000ms. Up to five rules are evaluated.",
  addRule: "Add Rule",
  noSlaRules: "No SLA Rules configured.",
  actionsHelp: "Runs always use the latest saved Test Plan revision.",
  expectedConcurrencyLabel: "Expected single-node concurrency",
  searchLabel: "Search test plans",
  searchPlaceholder: "Search by name",
  sortLabel: "Sort test plans",
  noEnvironment: "No environment",
  noNode: "No node",
  noNodes: "No idle Load Nodes are available for the selected pool.",
  noScenarios: "No saved Scenarios are available to add.",
  noTags: "No tags",
  selectPool: "Select pool",
  selectIdleNode: "Select an idle node",
  tagsPlaceholder: "checkout, baseline",
  revisionStatus: (revision: number, dirty: boolean) =>
    `Revision ${revision} · ${dirty ? "Unsaved changes" : "Saved"}`,
  expectedConcurrency: (value: number, softLimit: number) =>
    `Expected single-node concurrency: ${value} (soft limit ${softLimit})`,
  nodeOption: (host: string, status: string) => `${host} · ${status}`,
  loadSettingErrors: {
    termination: (index: number) =>
      `Scenario ${index}: choose hold-for or iterations.`,
    stepsRequireRampUp: (index: number) =>
      `Scenario ${index}: steps require ramp-up.`,
    targetRpsRequiresHoldFor: (index: number) =>
      `Scenario ${index}: target RPS requires hold-for.`,
  },
  slaRuleErrors: {
    responseCodePattern: (index: number) =>
      `SLA Rule ${index}: use a response code pattern like 500, 4??, or *.`,
  },
};
