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
