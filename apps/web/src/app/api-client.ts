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
