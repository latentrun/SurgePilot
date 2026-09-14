export const HELP_TABS = [
  { value: "getting-started", label: "Getting Started" },
  { value: "ai-agents", label: "AI Agents" },
  { value: "scripting", label: "Scripting" },
  { value: "api-catalog", label: "API Catalog" },
  { value: "troubleshooting", label: "Troubleshooting" },
  { value: "limits-activation", label: "Limits & Activation" },
] as const;

export const HELP_COPY = {
  loading: "Loading help...",
  topicsLabel: "Help topics",
  topicEyebrow: "Help topic",
  eyebrow: "Operator field guide",
  title: "Help",
  introduction:
    "Move from a configured workspace to repeatable performance tests, then connect approved tools without weakening SurgePilot's safety boundaries.",
  headerFacts: [
    { label: "Auth", value: "Session" },
    { label: "Context", value: "Workspace" },
    { label: "Safety", value: "Confirm" },
  ],
  gettingStarted: {
    title: "Start with a controlled test path",
    description:
      "Build one reusable flow, validate it with a Debug Run, then promote it into a Test Plan for standard execution.",
    steps: [
      {
        number: "01",
        title: "Prepare assets",
        body: "Create an Env Group, upload any required dependency files, and confirm the target Load Node is ready.",
      },
      {
        number: "02",
        title: "Model the flow",
        body: "Create a Scenario with explicit requests, variables, headers, and data sources. Use a Debug Run to inspect behavior.",
      },
      {
        number: "03",
        title: "Run with intent",
        body: "Add the Scenario to a Test Plan, review the execution preview, and confirm load settings before starting a run.",
      },
    ],
  },
  aiAgents: {
    title: "Use a user-owned local agent",
    description:
      "Connect a compatible local agent to SurgePilot through the governed Public API. SurgePilot provides source guidance, not an agent runtime or installer.",
    checklist: [
      "Create an API Key with only the scopes your workflow needs, and keep the plaintext token outside prompts, repositories, and logs.",
      "Copy the explicit Workspace ID from API Keys and send it as x-workspace-id with Public API requests.",
      "Use PAT Bearer authentication only with the /api/public/v1 surface documented by the bundled public-api.openapi.json snapshot.",
      "Keep calls inside the skill's current operationId allowlist and require confirmation before write operations.",
      "Extract the downloaded source, then point your own compatible local agent at SKILL.md using that agent's configuration model.",
    ],
    cards: [
      { title: "API Key", body: "Minimum scopes" },
      { title: "Public API", body: "Explicit context" },
      { title: "Safety", body: "Review writes" },
    ],
    archiveLabel: "Source zip",
    downloadTitle: "Official Public API skill source",
    downloadDescription:
      "Download the current repository-maintained source package. The archive is built for this request and is not an installer or release channel.",
    downloadButton: "Download official AI skill",
    downloadPending: "Preparing download...",
    downloadSuccess: "Download started.",
  },
  scripting: {
    title: "Keep executable intent visible",
    description:
      "Use Scenario steps and structured global configuration as the source of test behavior. SurgePilot renders the runtime configuration for you.",
    points: [
      "Prefer explicit HTTP steps and stable variables over hidden runtime assumptions.",
      "Use cURL import only as a draft accelerator; review URLs, headers, bodies, and extraction rules before saving.",
      "Use Debug Runs for focused validation before increasing concurrency or duration in a Test Plan.",
      "Editable Taurus YAML and arbitrary script execution are not part of the active product surface.",
    ],
  },
  apiCatalog: {
    title: "Treat API definitions as governed assets",
    description:
      "The API Catalog stores authorized OpenAPI or Swagger documents per Workspace and makes their operations available for inspection.",
    points: [
      "Upload JSON or YAML specifications through the API Catalog and verify validation status before use.",
      "Catalog entries remain isolated to the current Workspace and their source files stay in managed storage.",
      "Operation-assisted step drafting remains reviewable; the Catalog does not create complete Scenarios or Test Plans automatically.",
    ],
  },
  troubleshooting: {
    title: "Check the boundary that failed",
    description:
      "Start with the smallest relevant control plane signal instead of retrying a run with broader permissions or higher load.",
    points: [
      "Confirm Setup Status reports database and object storage readiness.",
      "Verify the selected Workspace, Env Group, dependency files, and API Catalog assets are the intended ones.",
      "Check Load Node connectivity and initialization before investigating a stalled or rejected run.",
      "Use the request ID from an API error when correlating a failure with server logs.",
    ],
  },
  limits: {
    title: "Know what is active",
    description:
      "Separate active system behavior from capabilities that remain intentionally unavailable.",
    activeTitle: "System bootstrap is active",
    activeBody:
      "After the first Admin registration, SurgePilot best-effort imports its own current curated Web/business OpenAPI into the Default Workspace API Catalog.",
    inactiveTitle: "External ingestion is inactive",
    inactiveBody:
      "SurgePilot does not automatically ingest user-provided URLs, external OpenAPI documents, repository specs, or arbitrary remote API definitions.",
    boundary:
      "This activation does not add an SDK, MCP server, marketplace, installer, built-in agent runtime, automatic Scenario generation, automatic tuning, or automatic report analysis.",
  },
  errors: {
    sessionExpired:
      "Your session has expired. Sign in again before downloading the skill.",
    sourceUnavailable:
      "Official skill source is temporarily unavailable. Try again later.",
    generic: "The skill download could not be started. Try again.",
  },
} as const;
