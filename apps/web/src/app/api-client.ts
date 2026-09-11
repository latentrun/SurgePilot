import type { components } from "@surgepilot/contracts/web-client";

export type UserRole = "admin" | "user";

export type ApiErrorBody = components["schemas"]["ErrorResponse"];
export type WorkspaceSummary = components["schemas"]["WorkspaceSummary"];
export type AvailableWorkspaceSummary =
  components["schemas"]["AvailableWorkspaceSummary"];
export type PermissionSummary = components["schemas"]["PermissionSummary"];
export type AuthSession = components["schemas"]["AuthSessionResponse"];
export type CsrfTokenResponse = components["schemas"]["CsrfTokenResponse"];
export type CurrentUser = components["schemas"]["CurrentUserResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type SetupStatus = components["schemas"]["SetupStatusResponse"];
export type UserSummary = components["schemas"]["UserSummary"];
export type WorkspaceWriteRequest = components["schemas"]["WorkspaceWriteRequest"];
export type WorkspaceEnvelope = components["schemas"]["WorkspaceEnvelope"];
export type AdminWorkspaceListResponse =
  components["schemas"]["AdminWorkspaceListResponse"];
export type AdminUserSummary = components["schemas"]["AdminUserSummary"];
export type AdminUserCreateRequest = components["schemas"]["AdminUserCreateRequest"];
export type AdminUserPatchRequest = components["schemas"]["AdminUserPatchRequest"];
export type AdminUserEnvelope = components["schemas"]["AdminUserEnvelope"];
export type AdminUserListResponse = components["schemas"]["AdminUserListResponse"];
export type SystemSettingsResponse = components["schemas"]["SystemSettingsResponse"];
export type SystemSettingsPatchRequest = components["schemas"]["SystemSettingsPatchRequest"];

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
export type DependencyFilePreviewResponse =
  components["schemas"]["DependencyFilePreviewResponse"];

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
export type MonitoringEmbedResponse =
  components["schemas"]["MonitoringEmbedResponse"];
export type RunMonitoringLinkResponse =
  components["schemas"]["RunMonitoringLinkResponse"];
export type CloneRequest = components["schemas"]["CloneRequest"];
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
export type CurlImportParseRequest =
  components["schemas"]["CurlImportParseRequest"];
export type CurlImportParseResponse =
  components["schemas"]["CurlImportParseResponse"];
export type CurlImportStepDraft = components["schemas"]["CurlImportStepDraft"];
export type OpenApiSpecSourceListResponse =
  components["schemas"]["OpenApiSpecSourceListResponse"];
export type OpenApiOperationListResponse =
  components["schemas"]["OpenApiOperationListResponse"];
export type OpenApiOperationRef = components["schemas"]["OpenApiOperationRef"];
export type OpenApiStepDraftGenerateRequest =
  components["schemas"]["OpenApiStepDraftGenerateRequest"];
export type OpenApiStepDraftPreviewResponse =
  components["schemas"]["OpenApiStepDraftPreviewResponse"];
export type OpenApiGeneratedStepDraft =
  components["schemas"]["OpenApiGeneratedStepDraft"];

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
export type ExecutionPreviewResponse =
  components["schemas"]["ExecutionPreviewResponse"];
export type ExecutionPreviewWarning =
  components["schemas"]["ExecutionPreviewWarning"];

export type OverviewActiveRuns =
  components["schemas"]["OverviewActiveRuns"];
export type OverviewRecentRun =
  components["schemas"]["OverviewRecentRun"];
export type OverviewResourceSummary =
  components["schemas"]["OverviewResourceSummary"];
export type OverviewResponse =
  components["schemas"]["OverviewResponse"];
export type OverviewResultRunScope =
  components["schemas"]["OverviewResultRunScope"];
export type OverviewRunStats =
  components["schemas"]["OverviewRunStats"];
export type OverviewStatsScope =
  components["schemas"]["OverviewStatsScope"];
export type OverviewWorkspace =
  components["schemas"]["OverviewWorkspace"];

export type ApiCatalogSpecListResponse =
  components["schemas"]["ApiCatalogSpecListResponse"];
export type ApiCatalogSpecResponse =
  components["schemas"]["ApiCatalogSpecResponse"];
export type ApiCatalogSpecSummary =
  components["schemas"]["ApiCatalogSpecSummary"];

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
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
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

export function getAdminSetupStatus() {
  return request<SetupStatus>("/v1/admin/setup-status");
}

export function getOverview(params: {
  recentLimit?: number;
  workspaceId: string;
}) {
  const query = new URLSearchParams();
  if (params.recentLimit !== undefined) {
    query.set("recentLimit", String(params.recentLimit));
  }
  const queryStr = query.toString();
  const url = queryStr ? `/v1/overview?${queryStr}` : "/v1/overview";
  return request<OverviewResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export function getCurrentUser(preferredWorkspaceId?: string | null) {
  const query = preferredWorkspaceId
    ? `?preferredWorkspaceId=${encodeURIComponent(preferredWorkspaceId)}`
    : "";
  return request<CurrentUser>(`/v1/auth/me${query}`);
}

export function getCsrfToken() {
  return request<CsrfTokenResponse>("/v1/auth/csrf");
}

export function listApiCatalogSpecs(params: {
  limit?: number;
  offset?: number;
  workspaceId: string;
}) {
  const query = new URLSearchParams({
    limit: String(params.limit ?? 50),
    offset: String(params.offset ?? 0),
  });
  return request<ApiCatalogSpecListResponse>(`/v1/api-catalog/specs?${query}`, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}

export async function uploadApiCatalogSpec(params: {
  file: File;
  name?: string;
  workspaceId: string;
  csrfToken: string;
}) {
  const formData = new FormData();
  formData.append("file", params.file);
  if (params.name?.trim()) formData.append("name", params.name.trim());
  return request<ApiCatalogSpecResponse>("/v1/api-catalog/specs", {
    method: "POST",
    headers: {
      "x-csrf-token": params.csrfToken,
      "x-workspace-id": params.workspaceId,
    },
    body: formData,
  });
}

export function getApiCatalogSpec(specId: string, workspaceId: string) {
  return request<ApiCatalogSpecResponse>(
    `/v1/api-catalog/specs/${encodeURIComponent(specId)}`,
    { headers: { "x-workspace-id": workspaceId } },
  );
}

export function deleteApiCatalogSpec(
  specId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return request<void>(
    `/v1/api-catalog/specs/${encodeURIComponent(specId)}`,
    {
      method: "DELETE",
      headers: {
        "x-csrf-token": csrfToken,
        "x-workspace-id": workspaceId,
      },
    },
  );
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

export function switchWorkspace(workspaceId: string, csrfToken: string) {
  return request<CurrentUser>("/v1/workspaces/switch", {
    method: "POST",
    body: JSON.stringify({ workspaceId }),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function listAdminWorkspaces(status: "active" | "archived" | "all" = "active") {
  return request<AdminWorkspaceListResponse>(
    `/v1/admin/workspaces?status=${encodeURIComponent(status)}`,
  );
}

export function createAdminWorkspace(payload: WorkspaceWriteRequest, csrfToken: string) {
  return request<WorkspaceEnvelope>("/v1/admin/workspaces", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function patchAdminWorkspace(id: string, payload: WorkspaceWriteRequest, csrfToken: string) {
  return request<WorkspaceEnvelope>(`/v1/admin/workspaces/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function archiveAdminWorkspace(id: string, csrfToken: string) {
  return request<WorkspaceEnvelope>(`/v1/admin/workspaces/${encodeURIComponent(id)}/archive`, {
    method: "POST",
    headers: { "x-csrf-token": csrfToken },
  });
}

export function listAdminUsers(q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return request<AdminUserListResponse>(`/v1/admin/users${query}`);
}

export function createAdminUser(payload: AdminUserCreateRequest, csrfToken: string) {
  return request<AdminUserEnvelope>("/v1/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function patchAdminUser(id: string, payload: AdminUserPatchRequest, csrfToken: string) {
  return request<AdminUserEnvelope>(`/v1/admin/users/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function replaceAdminUserWorkspaces(id: string, workspaceIds: string[], csrfToken: string) {
  return request<AdminUserEnvelope>(`/v1/admin/users/${encodeURIComponent(id)}/workspaces`, {
    method: "PUT",
    body: JSON.stringify({ workspaceIds }),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function resetAdminUserPassword(id: string, newPassword: string, csrfToken: string) {
  return request<{ user: AdminUserSummary }>(`/v1/admin/users/${encodeURIComponent(id)}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ newPassword }),
    headers: { "x-csrf-token": csrfToken },
  });
}

export function getSystemSettings() {
  return request<SystemSettingsResponse>("/v1/admin/system-settings");
}

export function patchSystemSettings(payload: SystemSettingsPatchRequest, csrfToken: string) {
  return request<SystemSettingsResponse>("/v1/admin/system-settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
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

export function previewDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
) {
  return request<DependencyFilePreviewResponse>(
    `/v1/dependency-files/${encodeURIComponent(dependencyFileId)}/preview`,
    {
      headers: { "x-workspace-id": workspaceId },
    },
  );
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

export function cloneScenario(
  scenarioId: string,
  payload: CloneRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<ScenarioDetail>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}/clone`,
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

export function parseScenarioCurlImport(
  payload: CurlImportParseRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<CurlImportParseResponse>(
    "/v1/scenarios/curl-import/parse",
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

export function listScenarioOpenApiSpecSources(
  scenarioId: string,
  workspaceId: string,
) {
  return request<OpenApiSpecSourceListResponse>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}/openapi-step-generation/specs`,
    { headers: { "x-workspace-id": workspaceId } },
  );
}

export function listScenarioOpenApiOperations(
  scenarioId: string,
  specId: string,
  workspaceId: string,
) {
  return request<OpenApiOperationListResponse>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}/openapi-step-generation/specs/${encodeURIComponent(specId)}/operations`,
    { headers: { "x-workspace-id": workspaceId } },
  );
}

export function generateScenarioOpenApiStepDrafts(
  scenarioId: string,
  payload: OpenApiStepDraftGenerateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<OpenApiStepDraftPreviewResponse>(
    `/v1/scenarios/${encodeURIComponent(scenarioId)}/openapi-step-generation/drafts`,
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

export function cloneTestPlan(
  testPlanId: string,
  payload: CloneRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return request<TestPlanDetail>(
    `/v1/test-plans/${encodeURIComponent(testPlanId)}/clone`,
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

export function getTestPlanExecutionPreview(params: {
  testPlanId: string;
  workspaceId: string;
  runType: "debug" | "standard";
}) {
  const query = new URLSearchParams({ runType: params.runType });
  return request<ExecutionPreviewResponse>(
    `/v1/test-plans/${encodeURIComponent(params.testPlanId)}/execution-preview?${query.toString()}`,
    { headers: { "x-workspace-id": params.workspaceId } },
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

export function getRunMonitoringLink(runId: string, workspaceId: string) {
  return request<RunMonitoringLinkResponse>(
    `/v1/runs/${encodeURIComponent(runId)}/monitoring`,
    { headers: { "x-workspace-id": workspaceId } },
  );
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

export function getMonitoringEmbed(params: {
  workspaceId: string;
  runId?: string | null;
  from?: string | null;
  to?: string | null;
}) {
  const query = new URLSearchParams();
  if (params.runId) query.set("runId", params.runId);
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);
  const queryStr = query.toString();
  const url = queryStr
    ? `/v1/monitoring/embed?${queryStr}`
    : "/v1/monitoring/embed";
  return request<MonitoringEmbedResponse>(url, {
    headers: { "x-workspace-id": params.workspaceId },
  });
}
