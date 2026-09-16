import createClient from "openapi-fetch";

import type { components, paths } from "@surgepilot/contracts/web-client";

export type ApiErrorBody = components["schemas"]["ErrorResponse"];
export type AuthSession = components["schemas"]["AuthSessionResponse"];
export type CurrentUser = components["schemas"]["CurrentUserResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type SetupStatus = components["schemas"]["SetupStatusResponse"];
export type ApiTokenCreateRequest =
  components["schemas"]["ApiTokenCreateRequest"];
export type ApiTokenCreateResponse =
  components["schemas"]["ApiTokenCreateResponse"];
export type ApiTokenListResponse =
  components["schemas"]["ApiTokenListResponse"];
export type ApiTokenMetadata = components["schemas"]["ApiTokenMetadata"];

export type WorkspaceSummary = components["schemas"]["WorkspaceSummary"];
export type AvailableWorkspaceSummary =
  components["schemas"]["AvailableWorkspaceSummary"];
export type PermissionSummary = components["schemas"]["PermissionSummary"];
export type WorkspaceWriteRequest =
  components["schemas"]["WorkspaceWriteRequest"];
export type WorkspaceEnvelope = components["schemas"]["WorkspaceEnvelope"];
export type AdminWorkspaceListResponse =
  components["schemas"]["AdminWorkspaceListResponse"];
export type AdminUserSummary = components["schemas"]["AdminUserSummary"];
export type AdminUserCreateRequest =
  components["schemas"]["AdminUserCreateRequest"];
export type AdminUserPatchRequest =
  components["schemas"]["AdminUserPatchRequest"];
export type AdminUserEnvelope = components["schemas"]["AdminUserEnvelope"];
export type AdminUserListResponse =
  components["schemas"]["AdminUserListResponse"];
export type MembershipReplaceRequest =
  components["schemas"]["MembershipReplaceRequest"];
export type SystemSettingsResponse =
  components["schemas"]["SystemSettingsResponse"];
export type SystemSettingsPatchRequest =
  components["schemas"]["SystemSettingsPatchRequest"];
export type OverviewResponse = components["schemas"]["OverviewResponse"];
export type ApiCatalogSpecListResponse =
  components["schemas"]["ApiCatalogSpecListResponse"];
export type ApiCatalogSpecResponse =
  components["schemas"]["ApiCatalogSpecResponse"];
export type ApiCatalogSpecSummary =
  components["schemas"]["ApiCatalogSpecSummary"];
export type ApiCatalogSpecSourceFormat =
  components["schemas"]["ApiCatalogSpecSourceFormat"];
export type ApiCatalogSpecStatus =
  components["schemas"]["ApiCatalogSpecStatus"];
export type OverviewRecentRun = components["schemas"]["OverviewRecentRun"];
export type EnvGroupCreateRequest =
  components["schemas"]["EnvGroupCreateRequest"];
export type EnvGroupDetail = components["schemas"]["EnvGroupDetail"];
export type EnvGroupListResponse =
  components["schemas"]["EnvGroupListResponse"];
export type EnvGroupPatchRequest =
  components["schemas"]["EnvGroupPatchRequest"];
export type EnvGroupSummary = components["schemas"]["EnvGroupSummary"];
export type EnvGroupVariableRead =
  | components["schemas"]["EnvGroupPlainVariableRead"]
  | components["schemas"]["EnvGroupSecretVariableRead"];
export type EnvGroupVariableWrite =
  | components["schemas"]["EnvGroupPlainVariableWrite"]
  | components["schemas"]["EnvGroupSecretVariableWrite"];
export type CloneRequest = components["schemas"]["CloneRequest"];
export type ExecutionPreviewResponse =
  components["schemas"]["ExecutionPreviewResponse"];
export type MonitoringEmbedResponse =
  components["schemas"]["MonitoringEmbedResponse"];
export type RunMonitoringLinkResponse =
  components["schemas"]["RunMonitoringLinkResponse"];

export type DependencyFileDetail =
  components["schemas"]["DependencyFileDetail"];
export type DependencyFileListResponse =
  components["schemas"]["DependencyFileListResponse"];
export type DependencyFilePreviewResponse =
  components["schemas"]["DependencyFilePreviewResponse"];
export type DependencyFileSummary =
  components["schemas"]["DependencyFileSummary"];
export type LoadNodeConnectivitySummary =
  components["schemas"]["LoadNodeConnectivitySummary"];
export type LoadNodeSummary = components["schemas"]["LoadNodeSummary"];
export type LoadNodeDetail = components["schemas"]["LoadNodeDetail"];
export type LoadNodeListResponse =
  components["schemas"]["LoadNodeListResponse"];
export type LoadNodeCreateRequest =
  components["schemas"]["LoadNodeCreateRequest"];
export type LoadNodePatchRequest =
  components["schemas"]["LoadNodePatchRequest"];
export type LoadNodeCredentialUpdateRequest =
  components["schemas"]["LoadNodeCredentialUpdateRequest"];
export type LoadNodeInitializeResponse =
  components["schemas"]["LoadNodeInitializeResponse"];
export type LoadNodeSshHostKeyInput =
  components["schemas"]["LoadNodeSshHostKeyInput"];
export type LoadNodeSshHostKeyResponse =
  components["schemas"]["LoadNodeSshHostKeyResponse"];
export type LoadNodeSshHostKeyScanRequest =
  components["schemas"]["LoadNodeSshHostKeyScanRequest"];
export type LoadNodeSshHostKeyScanResponse =
  components["schemas"]["LoadNodeSshHostKeyScanResponse"];
export type LoadNodeInitAttemptSummary =
  components["schemas"]["LoadNodeInitAttemptSummary"];
export type LoadNodeInitAttemptDetail =
  components["schemas"]["LoadNodeInitAttemptDetail"];
export type LoadNodeScope = components["schemas"]["LoadNodeSummary"]["scope"];
export type LoadNodeStatus = components["schemas"]["LoadNodeSummary"]["status"];
export type LoadNodeAuthType =
  components["schemas"]["LoadNodeSummary"]["authType"];
export type ScenarioCreateRequest =
  components["schemas"]["ScenarioCreateRequest"];
export type ScenarioDetail = components["schemas"]["ScenarioDetail"];
export type ScenarioListResponse =
  components["schemas"]["ScenarioListResponse"];
export type ScenarioPatchRequest =
  components["schemas"]["ScenarioPatchRequest"];
export type ScenarioStep = components["schemas"]["ScenarioStep"];
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
export type RunCreateRequest = components["schemas"]["RunCreateRequest"];
export type RunCreateResponse = components["schemas"]["RunCreateResponse"];
export type RunResourceRequest = components["schemas"]["RunResourceRequest"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type RunListItem = components["schemas"]["RunListItem"];
export type RunReportDetail = components["schemas"]["RunReportDetail"];
export type RunArtifactListResponse =
  components["schemas"]["RunArtifactListResponse"];
export type RunArtifactItem = components["schemas"]["RunArtifactItem"];
export type RunArtifactType = components["schemas"]["RunArtifactType"];
export type RunState = components["schemas"]["RunState"];
export type RunType = components["schemas"]["RunType"];
export type RunSourceType = components["schemas"]["RunSourceType"];
export type RunValidity = components["schemas"]["RunValidity"];
export type RunValidityPatchResponse =
  components["schemas"]["RunValidityPatchResponse"];
export type RunStopResponse = components["schemas"]["RunStopResponse"];
export type TestPlanCreateRequest =
  components["schemas"]["TestPlanCreateRequest"];
export type TestPlanDetail = components["schemas"]["TestPlanDetail"];
export type TestPlanListResponse =
  components["schemas"]["TestPlanListResponse"];
export type TestPlanPatchRequest =
  components["schemas"]["TestPlanPatchRequest"];
export type TestPlanSummary = components["schemas"]["TestPlanSummary"];
export type TestPlanScenarioItem =
  components["schemas"]["TestPlanScenarioItemDetail"];
export type TestPlanSlaRule = components["schemas"]["TestPlanSlaRuleDetail"];
export type TestPlanLoadSettings =
  components["schemas"]["TestPlanLoadSettings"];

export class ApiError extends Error {
  readonly body: ApiErrorBody;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.body = body;
    this.status = status;
  }
}

function defaultApiBaseUrl() {
  return typeof window === "undefined"
    ? "/api"
    : `${window.location.origin}/api`;
}

function normalizeApiBaseUrl(value: string | undefined) {
  const trimmed = value?.trim().replace(/\/+$/, "");
  return trimmed || defaultApiBaseUrl();
}

const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

const client = createClient<paths>({
  baseUrl: apiBaseUrl,
  credentials: "include",
  fetch: (input) => globalThis.fetch(input),
});

function fallbackError(): ApiErrorBody {
  return {
    code: "REQUEST_FAILED",
    message: "Request failed.",
    requestId: "unknown",
  };
}

async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const result = await request;
  if (!result.response.ok) {
    throw new ApiError(
      result.response.status,
      (result.error as ApiErrorBody | undefined) ?? fallbackError(),
    );
  }
  return result.data as T;
}

export function getSetupStatus() {
  return unwrap<SetupStatus>(client.GET("/v1/setup/status"));
}

export function downloadPublicApiAiSkill() {
  return unwrap<Blob>(
    client.GET("/v1/account/ai-skill/download", { parseAs: "blob" }),
  );
}

export function getAdminSetupStatus() {
  return unwrap<SetupStatus>(client.GET("/v1/admin/setup-status"));
}

export function listAdminWorkspaces(
  status: "active" | "archived" | "all" = "active",
) {
  return unwrap<AdminWorkspaceListResponse>(
    client.GET("/v1/admin/workspaces", { params: { query: { status } } }),
  );
}

export function createAdminWorkspace(
  payload: WorkspaceWriteRequest,
  csrfToken: string,
) {
  return unwrap<WorkspaceEnvelope>(
    client.POST("/v1/admin/workspaces", {
      body: payload,
      params: { header: { "x-csrf-token": csrfToken } },
    }),
  );
}

export function patchAdminWorkspace(
  workspaceId: string,
  payload: WorkspaceWriteRequest,
  csrfToken: string,
) {
  return unwrap<WorkspaceEnvelope>(
    client.PATCH("/v1/admin/workspaces/{workspaceId}", {
      body: payload,
      params: {
        path: { workspaceId },
        header: { "x-csrf-token": csrfToken },
      },
    }),
  );
}

export function archiveAdminWorkspace(workspaceId: string, csrfToken: string) {
  return unwrap<WorkspaceEnvelope>(
    client.POST("/v1/admin/workspaces/{workspaceId}/archive", {
      params: {
        path: { workspaceId },
        header: { "x-csrf-token": csrfToken },
      },
    }),
  );
}

export function listAdminUsers(q?: string) {
  return unwrap<AdminUserListResponse>(
    client.GET("/v1/admin/users", { params: { query: { q } } }),
  );
}

export function createAdminUser(
  payload: AdminUserCreateRequest,
  csrfToken: string,
) {
  return unwrap<AdminUserEnvelope>(
    client.POST("/v1/admin/users", {
      body: payload,
      params: { header: { "x-csrf-token": csrfToken } },
    }),
  );
}

export function patchAdminUser(
  userId: string,
  payload: AdminUserPatchRequest,
  csrfToken: string,
) {
  return unwrap<AdminUserEnvelope>(
    client.PATCH("/v1/admin/users/{userId}", {
      body: payload,
      params: {
        path: { userId },
        header: { "x-csrf-token": csrfToken },
      },
    }),
  );
}

export function resetAdminUserPassword(
  userId: string,
  newPassword: string,
  csrfToken: string,
) {
  return unwrap<AdminUserEnvelope>(
    client.POST("/v1/admin/users/{userId}/reset-password", {
      body: { newPassword },
      params: {
        path: { userId },
        header: { "x-csrf-token": csrfToken },
      },
    }),
  );
}

export function replaceAdminUserWorkspaces(
  userId: string,
  workspaceIds: string[],
  csrfToken: string,
) {
  return unwrap<AdminUserEnvelope>(
    client.PUT("/v1/admin/users/{userId}/workspaces", {
      body: { workspaceIds },
      params: {
        path: { userId },
        header: { "x-csrf-token": csrfToken },
      },
    }),
  );
}

export function getSystemSettings() {
  return unwrap<SystemSettingsResponse>(
    client.GET("/v1/admin/system-settings"),
  );
}

export function patchSystemSettings(
  payload: SystemSettingsPatchRequest,
  csrfToken: string,
) {
  return unwrap<SystemSettingsResponse>(
    client.PATCH("/v1/admin/system-settings", {
      body: payload,
      params: { header: { "x-csrf-token": csrfToken } },
    }),
  );
}

export function listApiCatalogSpecs(params: {
  limit?: number;
  offset?: number;
  workspaceId: string;
}) {
  return unwrap<ApiCatalogSpecListResponse>(
    client.GET("/v1/api-catalog/specs", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: { limit: params.limit ?? 50, offset: params.offset ?? 0 },
      },
    }),
  );
}

export function uploadApiCatalogSpec(params: {
  file: File;
  name?: string;
  workspaceId: string;
  csrfToken: string;
}) {
  const formData = new FormData();
  formData.append("file", params.file);
  const name = params.name?.trim();
  if (name) {
    formData.append("name", name);
  }
  return unwrap<ApiCatalogSpecResponse>(
    client.POST("/v1/api-catalog/specs", {
      body: formData as never,
      bodySerializer: (body) => body as unknown as BodyInit,
      params: {
        header: {
          "x-csrf-token": params.csrfToken,
          "x-workspace-id": params.workspaceId,
        },
      },
    }),
  );
}

export function getApiCatalogSpec(specId: string, workspaceId: string) {
  return unwrap<ApiCatalogSpecResponse>(
    client.GET("/v1/api-catalog/specs/{specId}", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { specId },
      },
    }),
  );
}

export function deleteApiCatalogSpec(
  specId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/api-catalog/specs/{specId}", {
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
        path: { specId },
      },
    }),
  );
}

export function getOverview(params: {
  recentLimit?: number;
  workspaceId: string;
}) {
  return unwrap<OverviewResponse>(
    client.GET("/v1/overview", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: { recentLimit: params.recentLimit ?? 5 },
      },
    }),
  );
}

export function listAccountApiTokens() {
  return unwrap<ApiTokenListResponse>(client.GET("/v1/account/api-tokens"));
}

export function createAccountApiToken(
  payload: ApiTokenCreateRequest,
  csrfToken: string,
) {
  return unwrap<ApiTokenCreateResponse>(
    client.POST("/v1/account/api-tokens", {
      body: payload,
      params: { header: { "x-csrf-token": csrfToken } },
    }),
  );
}

export function deleteAccountApiToken(tokenId: string, csrfToken: string) {
  return unwrap<void>(
    client.DELETE("/v1/account/api-tokens/{tokenId}", {
      params: {
        header: { "x-csrf-token": csrfToken },
        path: { tokenId },
      },
    }),
  );
}

export function getCurrentUser(preferredWorkspaceId?: string | null) {
  if (!preferredWorkspaceId) {
    return unwrap<CurrentUser>(client.GET("/v1/auth/me"));
  }
  return unwrap<CurrentUser>(
    client.GET("/v1/auth/me", {
      params: { query: { preferredWorkspaceId } },
    }),
  );
}

export function switchWorkspace(workspaceId: string, csrfToken: string) {
  return unwrap<CurrentUser>(
    client.POST("/v1/workspaces/switch", {
      body: { workspaceId },
      params: { header: { "x-csrf-token": csrfToken } },
    }),
  );
}

export function getCsrfToken() {
  return unwrap<components["schemas"]["CsrfTokenResponse"]>(
    client.GET("/v1/auth/csrf"),
  );
}

export function login(payload: LoginRequest) {
  return unwrap<AuthSession>(
    client.POST("/v1/auth/login", {
      body: payload,
    }),
  );
}

export function register(payload: RegisterRequest) {
  return unwrap<AuthSession>(
    client.POST("/v1/auth/register", {
      body: payload,
    }),
  );
}

export function logout(csrfToken: string) {
  return unwrap<void>(
    client.POST("/v1/auth/logout", {
      params: {
        header: {
          "x-csrf-token": csrfToken,
        },
      },
    }),
  );
}

export function listEnvGroups(params: {
  page?: number;
  pageSize?: number;
  q?: string;
  sort?: "name" | "createdAt" | "-createdAt";
  workspaceId: string;
}) {
  return unwrap<EnvGroupListResponse>(
    client.GET("/v1/env-groups", {
      params: {
        header: {
          "x-workspace-id": params.workspaceId,
        },
        query: {
          page: params.page ?? 1,
          pageSize: params.pageSize ?? 20,
          q: params.q || undefined,
          sort: params.sort ?? "-createdAt",
        },
      },
    }),
  );
}

export function getEnvGroup(envGroupId: string, workspaceId: string) {
  return unwrap<EnvGroupDetail>(
    client.GET("/v1/env-groups/{envGroupId}", {
      params: {
        header: {
          "x-workspace-id": workspaceId,
        },
        path: {
          envGroupId,
        },
      },
    }),
  );
}

export function createEnvGroup(
  payload: EnvGroupCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<EnvGroupDetail>(
    client.POST("/v1/env-groups", {
      body: payload,
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
      },
    }),
  );
}

export function patchEnvGroup(
  envGroupId: string,
  payload: EnvGroupPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<EnvGroupDetail>(
    client.PATCH("/v1/env-groups/{envGroupId}", {
      body: payload,
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
        path: {
          envGroupId,
        },
      },
    }),
  );
}

export function duplicateEnvGroup(
  envGroupId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<EnvGroupDetail>(
    client.POST("/v1/env-groups/{envGroupId}/duplicate", {
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
        path: {
          envGroupId,
        },
      },
    }),
  );
}

export function deleteEnvGroup(
  envGroupId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/env-groups/{envGroupId}", {
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
        path: {
          envGroupId,
        },
      },
    }),
  );
}

export function listDependencyFiles(params: {
  page?: number;
  pageSize?: number;
  q?: string;
  sort?: "filename" | "createdAt" | "-createdAt" | "sizeBytes" | "-sizeBytes";
  workspaceId: string;
}) {
  return unwrap<DependencyFileListResponse>(
    client.GET("/v1/dependency-files", {
      params: {
        header: {
          "x-workspace-id": params.workspaceId,
        },
        query: {
          page: params.page ?? 1,
          pageSize: params.pageSize ?? 20,
          q: params.q || undefined,
          sort: params.sort ?? "-createdAt",
        },
      },
    }),
  );
}

export function uploadDependencyFile(
  file: File,
  workspaceId: string,
  csrfToken: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  return unwrap<DependencyFileDetail>(
    client.POST("/v1/dependency-files", {
      body: formData as never,
      bodySerializer: (body) => body as unknown as BodyInit,
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
      },
    }),
  );
}

export function getDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
) {
  return unwrap<DependencyFileDetail>(
    client.GET("/v1/dependency-files/{dependencyFileId}", {
      params: {
        header: {
          "x-workspace-id": workspaceId,
        },
        path: {
          dependencyFileId,
        },
      },
    }),
  );
}

export function downloadDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
) {
  return unwrap<Blob>(
    client.GET("/v1/dependency-files/{dependencyFileId}/download", {
      parseAs: "blob",
      params: {
        header: {
          "x-workspace-id": workspaceId,
        },
        path: {
          dependencyFileId,
        },
      },
    }),
  );
}

export function previewDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
) {
  return unwrap<DependencyFilePreviewResponse>(
    client.GET("/v1/dependency-files/{dependencyFileId}/preview", {
      params: {
        header: {
          "x-workspace-id": workspaceId,
        },
        path: {
          dependencyFileId,
        },
      },
    }),
  );
}

export function deleteDependencyFile(
  dependencyFileId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/dependency-files/{dependencyFileId}", {
      params: {
        header: {
          "x-csrf-token": csrfToken,
          "x-workspace-id": workspaceId,
        },
        path: {
          dependencyFileId,
        },
      },
    }),
  );
}

export function getLoadNodeConnectivitySummary() {
  return unwrap<LoadNodeConnectivitySummary>(
    client.GET("/v1/load-nodes/connectivity-summary"),
  );
}

export function listLoadNodes(params: {
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
  q?: string;
  scope?: LoadNodeScope | "";
  sort?:
    | "createdAt"
    | "-createdAt"
    | "host"
    | "status"
    | "lastCheckedAt"
    | "-lastCheckedAt";
  status?: LoadNodeStatus | "";
  workspaceId: string;
}) {
  return unwrap<LoadNodeListResponse>(
    client.GET("/v1/load-nodes", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: {
          includeArchived: params.includeArchived || undefined,
          limit: params.limit ?? 20,
          offset: params.offset ?? 0,
          q: params.q || undefined,
          scope: params.scope || undefined,
          sort: params.sort ?? "-createdAt",
          status: params.status || undefined,
        },
      },
    }),
  );
}

export function createLoadNode(
  payload: LoadNodeCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeDetail>(
    client.POST("/v1/load-nodes", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function scanLoadNodeSshHostKey(
  payload: LoadNodeSshHostKeyScanRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeSshHostKeyScanResponse>(
    client.POST("/v1/load-nodes/ssh-host-key/scan", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function patchLoadNode(
  loadNodeId: string,
  payload: LoadNodePatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeDetail>(
    client.PATCH("/v1/load-nodes/{loadNodeId}", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function trustLoadNodeSshHostKey(
  loadNodeId: string,
  payload: LoadNodeSshHostKeyInput,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeDetail>(
    client.POST("/v1/load-nodes/{loadNodeId}/ssh-host-key/trust", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function updateLoadNodeCredentials(
  loadNodeId: string,
  payload: LoadNodeCredentialUpdateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeDetail>(
    client.POST("/v1/load-nodes/{loadNodeId}/credentials", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function initializeLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
  force = false,
) {
  return unwrap<LoadNodeInitializeResponse>(
    client.POST("/v1/load-nodes/{loadNodeId}/initialize", {
      body: { force },
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function listLoadNodeInitAttempts(
  loadNodeId: string,
  workspaceId: string,
  limit = 20,
  offset = 0,
) {
  return unwrap<components["schemas"]["LoadNodeInitAttemptListResponse"]>(
    client.GET("/v1/load-nodes/{loadNodeId}/init-attempts", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { loadNodeId },
        query: { limit, offset },
      },
    }),
  );
}

export function getLoadNodeInitAttempt(
  loadNodeId: string,
  attemptId: string,
  workspaceId: string,
) {
  return unwrap<LoadNodeInitAttemptDetail>(
    client.GET("/v1/load-nodes/{loadNodeId}/init-attempts/{attemptId}", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { loadNodeId, attemptId },
      },
    }),
  );
}

export function disableLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
  reason?: string,
) {
  return unwrap<LoadNodeDetail>(
    client.POST("/v1/load-nodes/{loadNodeId}/disable", {
      body: { reason },
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function enableLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<LoadNodeDetail>(
    client.POST("/v1/load-nodes/{loadNodeId}/enable", {
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function deleteLoadNode(
  loadNodeId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/load-nodes/{loadNodeId}", {
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { loadNodeId },
      },
    }),
  );
}

export function listScenarios(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: "-updatedAt" | "updatedAt" | "name" | "-name";
  workspaceId: string;
}) {
  return unwrap<ScenarioListResponse>(
    client.GET("/v1/scenarios", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: {
          page: params.page ?? 1,
          pageSize: params.pageSize ?? 20,
          search: params.search || undefined,
          sort: params.sort ?? "-updatedAt",
        },
      },
    }),
  );
}

export function createScenario(
  payload: ScenarioCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<ScenarioDetail>(
    client.POST("/v1/scenarios", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function getScenario(scenarioId: string, workspaceId: string) {
  return unwrap<ScenarioDetail>(
    client.GET("/v1/scenarios/{scenarioId}", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function cloneScenario(
  scenarioId: string,
  payload: CloneRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<ScenarioDetail>(
    client.POST("/v1/scenarios/{scenarioId}/clone", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function patchScenario(
  scenarioId: string,
  payload: ScenarioPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<ScenarioDetail>(
    client.PATCH("/v1/scenarios/{scenarioId}", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function deleteScenario(
  scenarioId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/scenarios/{scenarioId}", {
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function parseScenarioCurlImport(
  payload: CurlImportParseRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<CurlImportParseResponse>(
    client.POST("/v1/scenarios/curl-import/parse", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function listScenarioOpenApiSpecSources(
  scenarioId: string,
  workspaceId: string,
) {
  return unwrap<OpenApiSpecSourceListResponse>(
    client.GET("/v1/scenarios/{scenarioId}/openapi-step-generation/specs", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function listScenarioOpenApiOperations(
  scenarioId: string,
  specId: string,
  workspaceId: string,
) {
  return unwrap<OpenApiOperationListResponse>(
    client.GET(
      "/v1/scenarios/{scenarioId}/openapi-step-generation/specs/{specId}/operations",
      {
        params: {
          header: { "x-workspace-id": workspaceId },
          path: { scenarioId, specId },
        },
      },
    ),
  );
}

export function generateScenarioOpenApiStepDrafts(
  scenarioId: string,
  payload: OpenApiStepDraftGenerateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<OpenApiStepDraftPreviewResponse>(
    client.POST("/v1/scenarios/{scenarioId}/openapi-step-generation/drafts", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { scenarioId },
      },
    }),
  );
}

export function listTestPlans(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  tag?: string;
  sort?: "-updatedAt" | "updatedAt" | "name" | "-name";
  workspaceId: string;
}) {
  return unwrap<TestPlanListResponse>(
    client.GET("/v1/test-plans", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: {
          page: params.page ?? 1,
          pageSize: params.pageSize ?? 20,
          search: params.search || undefined,
          tag: params.tag || undefined,
          sort: params.sort ?? "-updatedAt",
        },
      },
    }),
  );
}

export function createTestPlan(
  payload: TestPlanCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<TestPlanDetail>(
    client.POST("/v1/test-plans", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function getTestPlan(testPlanId: string, workspaceId: string) {
  return unwrap<TestPlanDetail>(
    client.GET("/v1/test-plans/{testPlanId}", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { testPlanId },
      },
    }),
  );
}

export function cloneTestPlan(
  testPlanId: string,
  payload: CloneRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<TestPlanDetail>(
    client.POST("/v1/test-plans/{testPlanId}/clone", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { testPlanId },
      },
    }),
  );
}

export function getTestPlanExecutionPreview(params: {
  testPlanId: string;
  workspaceId: string;
  runType: "debug" | "standard";
}) {
  return unwrap<ExecutionPreviewResponse>(
    client.GET("/v1/test-plans/{testPlanId}/execution-preview", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        path: { testPlanId: params.testPlanId },
        query: { runType: params.runType },
      },
    }),
  );
}

export function patchTestPlan(
  testPlanId: string,
  payload: TestPlanPatchRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<TestPlanDetail>(
    client.PATCH("/v1/test-plans/{testPlanId}", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { testPlanId },
      },
    }),
  );
}

export function deleteTestPlan(
  testPlanId: string,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<void>(
    client.DELETE("/v1/test-plans/{testPlanId}", {
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { testPlanId },
      },
    }),
  );
}

export function createRun(
  payload: RunCreateRequest,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<RunCreateResponse>(
    client.POST("/v1/runs", {
      body: payload,
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      },
    }),
  );
}

export function listRuns(params: {
  cursor?: string | null;
  limit?: number;
  q?: string;
  recentHours?: number;
  runType?: RunType | "";
  sourceType?: RunSourceType | "";
  state?: RunState | "";
  tag?: string;
  validity?: RunValidity | "";
  workspaceId: string;
}) {
  return unwrap<RunListResponse>(
    client.GET("/v1/runs", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: {
          cursor: params.cursor || undefined,
          limit: params.limit ?? 20,
          q: params.q || undefined,
          recentHours: params.recentHours,
          runType: params.runType || undefined,
          sort: "-createdAt",
          sourceType: params.sourceType || undefined,
          state: params.state || undefined,
          tag: params.tag || undefined,
          validity: params.validity || undefined,
        },
      },
    }),
  );
}

export function getRunReport(runId: string, workspaceId: string) {
  return unwrap<RunReportDetail>(
    client.GET("/v1/runs/{runId}", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { runId },
      },
    }),
  );
}

export function getRunMonitoringLink(runId: string, workspaceId: string) {
  return unwrap<RunMonitoringLinkResponse>(
    client.GET("/v1/runs/{runId}/monitoring", {
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { runId },
      },
    }),
  );
}

export function getMonitoringEmbed(params: {
  workspaceId: string;
  runId?: string | null;
  from?: string | null;
  to?: string | null;
}) {
  return unwrap<MonitoringEmbedResponse>(
    client.GET("/v1/monitoring/embed", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        query: {
          runId: params.runId || undefined,
          from: params.from || undefined,
          to: params.to || undefined,
        },
      },
    }),
  );
}

export function listRunArtifacts(params: {
  artifactType?: RunArtifactType;
  cursor?: string | null;
  limit?: number;
  sort?: "createdAt" | "-createdAt";
  runId: string;
  workspaceId: string;
}) {
  return unwrap<RunArtifactListResponse>(
    client.GET("/v1/runs/{runId}/artifacts", {
      params: {
        header: { "x-workspace-id": params.workspaceId },
        path: { runId: params.runId },
        query: {
          artifactType: params.artifactType,
          cursor: params.cursor || undefined,
          limit: params.limit ?? 50,
          sort: params.sort ?? "createdAt",
        },
      },
    }),
  );
}

export function downloadRunArtifact(
  runId: string,
  artifactId: string,
  workspaceId: string,
) {
  return unwrap<Blob>(
    client.GET("/v1/runs/{runId}/artifacts/{artifactId}/download", {
      parseAs: "blob",
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { runId, artifactId },
      },
    }),
  );
}

export function downloadDebugHttpBodyBlob(
  runId: string,
  artifactId: string,
  workspaceId: string,
) {
  return unwrap<Blob>(
    client.GET("/v1/runs/{runId}/debug-http-body-blobs/{artifactId}/download", {
      parseAs: "blob",
      params: {
        header: { "x-workspace-id": workspaceId },
        path: { runId, artifactId },
      },
    }),
  );
}

export function patchRunValidity(
  runId: string,
  validity: RunValidity,
  workspaceId: string,
  csrfToken: string,
) {
  return unwrap<RunValidityPatchResponse>(
    client.PATCH("/v1/runs/{runId}/validity", {
      body: { validity },
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { runId },
      },
    }),
  );
}

export function stopRun(runId: string, workspaceId: string, csrfToken: string) {
  return unwrap<RunStopResponse>(
    client.POST("/v1/runs/{runId}/stop", {
      params: {
        header: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
        path: { runId },
      },
    }),
  );
}
