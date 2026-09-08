import type { components } from "@surgepilot/contracts/web-client";

export type UserRole = "admin" | "user";

export type ApiErrorBody = components["schemas"]["ErrorResponse"];
export type AuthSession = components["schemas"]["AuthSessionResponse"];
export type CsrfTokenResponse = components["schemas"]["CsrfTokenResponse"];
export type CurrentUser = components["schemas"]["CurrentUserResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type SetupStatus = components["schemas"]["SetupStatusResponse"];
export type UserSummary = components["schemas"]["UserSummary"];
export type WorkspaceSummary = components["schemas"]["WorkspaceSummary"];

export type EnvGroupCreateRequest =
  components["schemas"]["EnvGroupCreateRequest"];
export type EnvGroupDetail = components["schemas"]["EnvGroupDetail"];
export type EnvGroupListResponse =
  components["schemas"]["EnvGroupListResponse"];
export type EnvGroupPatchRequest =
  components["schemas"]["EnvGroupPatchRequest"];
export type EnvGroupSummary = components["schemas"]["EnvGroupSummary"];

export type DependencyFileDetail =
  components["schemas"]["DependencyFileDetail"];
export type DependencyFileListResponse =
  components["schemas"]["DependencyFileListResponse"];
export type DependencyFileSummary =
  components["schemas"]["DependencyFileSummary"];

export type LoadNodeCreateRequest =
  components["schemas"]["LoadNodeCreateRequest"];
export type LoadNodeCredentialUpdateRequest =
  components["schemas"]["LoadNodeCredentialUpdateRequest"];
export type LoadNodeDetail = components["schemas"]["LoadNodeDetail"];
export type LoadNodeInitAttemptDetail =
  components["schemas"]["LoadNodeInitAttemptDetail"];
export type LoadNodeInitAttemptListResponse =
  components["schemas"]["LoadNodeInitAttemptListResponse"];
export type LoadNodeInitAttemptSummary =
  components["schemas"]["LoadNodeInitAttemptSummary"];
export type LoadNodeInitializeResponse =
  components["schemas"]["LoadNodeInitializeResponse"];
export type LoadNodeListResponse =
  components["schemas"]["LoadNodeListResponse"];
export type LoadNodePatchRequest =
  components["schemas"]["LoadNodePatchRequest"];
export type LoadNodeScope =
  components["schemas"]["LoadNodeSummary"]["scope"];
export type LoadNodeStatus =
  components["schemas"]["LoadNodeSummary"]["status"];
export type LoadNodeAuthType =
  components["schemas"]["LoadNodeSummary"]["authType"];
export type LoadNodeSshHostKeyInput =
  components["schemas"]["LoadNodeSshHostKeyInput"];
export type LoadNodeSshHostKeyResponse =
  components["schemas"]["LoadNodeSshHostKeyResponse"];
export type LoadNodeSshHostKeyScanRequest =
  components["schemas"]["LoadNodeSshHostKeyScanRequest"];
export type LoadNodeSshHostKeyScanResponse =
  components["schemas"]["LoadNodeSshHostKeyScanResponse"];
export type LoadNodeSummary = components["schemas"]["LoadNodeSummary"];

export type RunCreateRequest = components["schemas"]["RunCreateRequest"];
export type RunCreateResponse = components["schemas"]["RunCreateResponse"];
export type RunState = components["schemas"]["RunState"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type RunListItem = components["schemas"]["RunListItem"];
export type RunReportDetail = components["schemas"]["RunReportDetail"];
export type RunArtifactListResponse = components["schemas"]["RunArtifactListResponse"];
export type RunArtifactItem = components["schemas"]["RunArtifactItem"];
export type RunArtifactType = components["schemas"]["RunArtifactType"];
export type RunType = components["schemas"]["RunType"];
export type RunSourceType = components["schemas"]["RunSourceType"];
export type RunValidity = components["schemas"]["RunValidity"];
export type RunValidityPatchResponse = components["schemas"]["RunValidityPatchResponse"];
export type RunStopResponse = components["schemas"]["RunStopResponse"];
export type ScenarioAssertion = components["schemas"]["ScenarioAssertion"];
export type ScenarioBody = components["schemas"]["ScenarioBody"];
export type ScenarioCreateRequest =
  components["schemas"]["ScenarioCreateRequest"];
export type ScenarioDataSource =
  components["schemas"]["ScenarioDataSource"];
export type ScenarioDefaultSettings =
  components["schemas"]["ScenarioDefaultSettings"];
export type ScenarioDetail = components["schemas"]["ScenarioDetail"];
export type ScenarioExtractor = components["schemas"]["ScenarioExtractor"];
export type ScenarioFormField = components["schemas"]["ScenarioFormField"];
export type ScenarioListResponse =
  components["schemas"]["ScenarioListResponse"];
export type ScenarioNamedValue = components["schemas"]["ScenarioNamedValue"];
export type ScenarioPatchRequest =
  components["schemas"]["ScenarioPatchRequest"];
export type ScenarioScript = components["schemas"]["ScenarioScript"];
export type ScenarioStep = components["schemas"]["ScenarioStep"];
export type ScenarioStepSettings =
  components["schemas"]["ScenarioStepSettings"];
export type ScenarioSummary = components["schemas"]["ScenarioSummary"];
export type ScenarioUploadFile = components["schemas"]["ScenarioUploadFile"];

export type TestPlanCreateRequest =
  components["schemas"]["TestPlanCreateRequest"];
export type TestPlanDetail = components["schemas"]["TestPlanDetail"];
export type TestPlanListResponse =
  components["schemas"]["TestPlanListResponse"];
export type TestPlanLoadSettings =
  components["schemas"]["TestPlanLoadSettings"];
export type TestPlanPatchRequest =
  components["schemas"]["TestPlanPatchRequest"];
export type TestPlanSummary = components["schemas"]["TestPlanSummary"];
export type TestPlanScenarioItem =
  components["schemas"]["TestPlanScenarioItemDetail"];
export type TestPlanSlaRule = components["schemas"]["TestPlanSlaRuleDetail"];

export class ApiError extends Error {
  readonly body: ApiErrorBody;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function apiUrl(path: string) {
  const base = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
  return `${base || "/api"}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body) headers.set("Content-Type", "application/json");
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError(0, {
      code: "REQUEST_FAILED",
      message: "Request failed.",
    });
  }

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { code: "REQUEST_FAILED", message: "Request failed." };
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getSetupStatus() {
  return request<SetupStatus>("/v1/setup/status");
}

export function getCurrentUser() {
  return request<CurrentUser>("/v1/auth/me");
}

export function getCsrfToken() {
  return request<CsrfTokenResponse>("/v1/auth/csrf");
}

export function login(payload: LoginRequest) {
  return request<AuthSession>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterRequest) {
  return request<AuthSession>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout(csrfToken: string) {
  return request<void>("/v1/auth/logout", {
    method: "POST",
    headers: { "x-csrf-token": csrfToken },
  });
}

export function listEnvGroups(params: {
  page?: number;
  pageSize?: number;
  q?: string;
  sort?: string;
  workspaceId: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set("page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    searchParams.set("pageSize", String(params.pageSize));
  }
  if (params.q) {
    searchParams.set("q", params.q);
  }
  if (params.sort) {
    searchParams.set("sort", params.sort);
  }
  const queryStr = searchParams.toString();
  const url = queryStr ? `/v1/env-groups?${queryStr}` : "/v1/env-groups";
  return request<EnvGroupListResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function getEnvGroup(envGroupId: string, workspaceId: string) {
  return request<EnvGroupDetail>(
    `/v1/env-groups/${encodeURIComponent(envGroupId)}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export function createEnvGroup(
  payload: EnvGroupCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<EnvGroupDetail>("/v1/env-groups", {
    method: "POST",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
    body: JSON.stringify(payload),
  });
}

export function patchEnvGroup(
  envGroupId: string,
  payload: EnvGroupPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<EnvGroupDetail>(
    `/v1/env-groups/${encodeURIComponent(envGroupId)}`,
    {
      method: "PATCH",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function duplicateEnvGroup(
  envGroupId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<EnvGroupDetail>(
    `/v1/env-groups/${encodeURIComponent(envGroupId)}/duplicate`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function deleteEnvGroup(
  envGroupId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(
    `/v1/env-groups/${encodeURIComponent(envGroupId)}`,
    {
      method: "DELETE",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function listDependencyFiles(params: {
  page?: number;
  pageSize?: number;
  q?: string;
  sort?: string;
  workspaceId: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set("page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    searchParams.set("pageSize", String(params.pageSize));
  }
  if (params.q) {
    searchParams.set("q", params.q);
  }
  if (params.sort) {
    searchParams.set("sort", params.sort);
  }
  const queryStr = searchParams.toString();
  const url = queryStr
    ? `/v1/dependency-files?${queryStr}`
    : "/v1/dependency-files";
  return request<DependencyFileListResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function getDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
) {
  return request<DependencyFileDetail>(
    `/v1/dependency-files/${encodeURIComponent(dependencyFileId)}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export async function uploadDependencyFile(
  file: File,
  workspaceId: string,
  csrfToken: string,
): Promise<DependencyFileDetail> {
  const formData = new FormData();
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(apiUrl("/v1/dependency-files"), {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: formData,
    });
  } catch {
    throw new ApiError(0, {
      code: "REQUEST_FAILED",
      message: "Request failed.",
    });
  }

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { code: "REQUEST_FAILED", message: "Request failed." };
    }
    throw new ApiError(response.status, body);
  }

  return (await response.json()) as DependencyFileDetail;
}

export async function downloadDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(
      apiUrl(
        `/v1/dependency-files/${encodeURIComponent(dependencyFileId)}/download`,
      ),
      {
        method: "GET",
        credentials: "include",
        headers: {
          "x-workspace-id": workspaceId,
        },
      },
    );
  } catch {
    throw new ApiError(0, {
      code: "REQUEST_FAILED",
      message: "Request failed.",
    });
  }

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { code: "REQUEST_FAILED", message: "Request failed." };
    }
    throw new ApiError(response.status, body);
  }

  return await response.blob();
}

export function deleteDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(
    `/v1/dependency-files/${encodeURIComponent(dependencyFileId)}`,
    {
      method: "DELETE",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function listLoadNodes(params: {
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
  q?: string;
  scope?: LoadNodeScope | "";
  sort?: string;
  status?: LoadNodeStatus | "";
  workspaceId: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.limit !== undefined) {
    searchParams.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    searchParams.set("offset", String(params.offset));
  }
  if (params.q) {
    searchParams.set("q", params.q);
  }
  if (params.scope) {
    searchParams.set("scope", params.scope);
  }
  if (params.status) {
    searchParams.set("status", params.status);
  }
  if (params.sort) {
    searchParams.set("sort", params.sort);
  }
  if (params.includeArchived !== undefined) {
    searchParams.set("includeArchived", String(params.includeArchived));
  }
  const queryStr = searchParams.toString();
  const url = queryStr ? `/v1/load-nodes?${queryStr}` : "/v1/load-nodes";
  return request<LoadNodeListResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function createLoadNode(
  payload: LoadNodeCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeDetail>("/v1/load-nodes", {
    method: "POST",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
    body: JSON.stringify(payload),
  });
}

export function scanLoadNodeSshHostKey(
  payload: LoadNodeSshHostKeyScanRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeSshHostKeyScanResponse>(
    "/v1/load-nodes/ssh-host-key/scan",
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function patchLoadNode(
  loadNodeId: string,
  payload: LoadNodePatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}`,
    {
      method: "PATCH",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function trustLoadNodeSshHostKey(
  loadNodeId: string,
  payload: LoadNodeSshHostKeyInput,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/ssh-host-key/trust`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function updateLoadNodeCredentials(
  loadNodeId: string,
  payload: LoadNodeCredentialUpdateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/credentials`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function initializeLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
  force = false,
) {
  return request<LoadNodeInitializeResponse>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/initialize`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify({ force }),
    },
  );
}

export function listLoadNodeInitAttempts(
  loadNodeId: string,
  workspaceId: string,
  limit = 20,
  offset = 0,
) {
  const searchParams = new URLSearchParams();
  searchParams.set("limit", String(limit));
  searchParams.set("offset", String(offset));
  return request<LoadNodeInitAttemptListResponse>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/init-attempts?${searchParams.toString()}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export function getLoadNodeInitAttempt(
  loadNodeId: string,
  attemptId: string,
  workspaceId: string,
) {
  return request<LoadNodeInitAttemptDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/init-attempts/${encodeURIComponent(attemptId)}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export function disableLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
  reason?: string,
) {
  return request<LoadNodeDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/disable`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(reason ? { reason } : {}),
    },
  );
}

export function enableLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<LoadNodeDetail>(
    `/v1/load-nodes/${encodeURIComponent(loadNodeId)}/enable`,
    {
      method: "POST",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function deleteLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(`/v1/load-nodes/${encodeURIComponent(loadNodeId)}`, {
    method: "DELETE",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
  });
}

export function listScenarios(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: "-updatedAt" | "updatedAt" | "name" | "-name";
  workspaceId: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set("page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    searchParams.set("pageSize", String(params.pageSize));
  }
  if (params.search) {
    searchParams.set("search", params.search);
  }
  if (params.sort) {
    searchParams.set("sort", params.sort);
  }
  const queryStr = searchParams.toString();
  const url = queryStr ? `/v1/scenarios?${queryStr}` : "/v1/scenarios";
  return request<ScenarioListResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function getScenario(scenarioId: string, workspaceId: string) {
  return request<ScenarioDetail>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export function createScenario(
  payload: ScenarioCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<ScenarioDetail>("/v1/scenarios", {
    method: "POST",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
    body: JSON.stringify(payload),
  });
}

export function patchScenario(
  scenarioId: string,
  payload: ScenarioPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<ScenarioDetail>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}`,
    {
      method: "PATCH",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function deleteScenario(
  scenarioId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}`,
    {
      method: "DELETE",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function listTestPlans(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: "-updatedAt" | "updatedAt" | "name" | "-name";
  workspaceId: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set("page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    searchParams.set("pageSize", String(params.pageSize));
  }
  if (params.search) {
    searchParams.set("search", params.search);
  }
  if (params.sort) {
    searchParams.set("sort", params.sort);
  }
  const queryStr = searchParams.toString();
  const url = queryStr ? `/v1/test-plans?${queryStr}` : "/v1/test-plans";
  return request<TestPlanListResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function createTestPlan(
  payload: TestPlanCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<TestPlanDetail>("/v1/test-plans", {
    method: "POST",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
    body: JSON.stringify(payload),
  });
}

export function getTestPlan(testPlanId: string, workspaceId: string) {
  return request<TestPlanDetail>(
    `/v1/test-plans/${encodeURIComponent(testPlanId)}`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
}

export function patchTestPlan(
  testPlanId: string,
  payload: TestPlanPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<TestPlanDetail>(
    `/v1/test-plans/${encodeURIComponent(testPlanId)}`,
    {
      method: "PATCH",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function deleteTestPlan(
  testPlanId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(
    `/v1/test-plans/${encodeURIComponent(testPlanId)}`,
    {
      method: "DELETE",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
}

export function createRun(
  payload: RunCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<RunCreateResponse>("/v1/runs", {
    method: "POST",
    headers: {
      "x-csrf-token": csrfToken,
      "x-workspace-id": workspaceId,
    },
    body: JSON.stringify(payload),
  });
}

export function listRuns(params: {
  cursor?: string | null;
  limit?: number;
  q?: string;
  recentHours?: number;
  runType?: RunType | "";
  sourceType?: RunSourceType | "";
  state?: RunState | "";
  validity?: RunValidity | "";
  workspaceId: string;
}) {
  const query = new URLSearchParams();
  if (params.cursor) query.set("cursor", params.cursor);
  query.set("limit", String(params.limit ?? 20));
  if (params.q) query.set("q", params.q);
  if (params.recentHours) query.set("recentHours", String(params.recentHours));
  if (params.runType) query.set("runType", params.runType);
  if (params.sourceType) query.set("sourceType", params.sourceType);
  if (params.state) query.set("state", params.state);
  if (params.validity) query.set("validity", params.validity);
  query.set("sort", "-createdAt");
  return request<RunListResponse>(`/v1/runs?${query.toString()}`, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function getRunReport(runId: string, workspaceId: string) {
  return request<RunReportDetail>(`/v1/runs/${encodeURIComponent(runId)}`, {
    headers: { "x-workspace-id": workspaceId },
  });
}

export function listRunArtifacts(params: {
  runId: string;
  workspaceId: string;
  cursor?: string | null;
}) {
  const query = new URLSearchParams({ limit: "50", sort: "createdAt" });
  if (params.cursor) query.set("cursor", params.cursor);
  return request<RunArtifactListResponse>(
    `/v1/runs/${encodeURIComponent(params.runId)}/artifacts?${query.toString()}`,
    { headers: { "x-workspace-id": params.workspaceId } },
  );
}

export function downloadRunArtifact(
  runId: string,
  artifactId: string,
  workspaceId: string,
) {
  return fetch(apiUrl(`/v1/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}/download`), {
    credentials: "include",
    headers: { "x-workspace-id": workspaceId },
  }).then(async (response) => {
    if (!response.ok) throw new ApiError(response.status, await response.json());
    return response.blob();
  });
}

export function patchRunValidity(
  runId: string,
  validity: RunValidity,
  workspaceId: string,
  csrfToken: string,
) {
  return request<RunValidityPatchResponse>(`/v1/runs/${encodeURIComponent(runId)}/validity`, {
    method: "PATCH",
    headers: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
    body: JSON.stringify({ validity }),
  });
}

export function stopRun(runId: string, workspaceId: string, csrfToken: string) {
  return request<RunStopResponse>(`/v1/runs/${encodeURIComponent(runId)}/stop`, {
    method: "POST",
    headers: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
  });
}
