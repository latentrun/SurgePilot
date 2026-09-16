import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ApiError,
  type AuthSession,
  type CurrentUser,
  getCsrfToken,
  getCurrentUser,
  login,
  logout,
  register,
  switchWorkspace as switchWorkspaceRequest,
} from "./api-client";
import type { LoginRequest, RegisterRequest } from "./api-client";

type SessionData = Pick<
  AuthSession,
  | "availableWorkspaces"
  | "currentWorkspace"
  | "defaultWorkspace"
  | "permissions"
  | "user"
>;

type AuthSessionContextValue = {
  csrfToken: string | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  postLogoutRedirectPath: "/" | null;
  session: SessionData | null;
  clearPostLogoutRedirect: () => void;
  signIn: (payload: LoginRequest) => Promise<AuthSession>;
  signOut: (options?: { redirectPath?: "/" }) => Promise<void>;
  signUp: (payload: RegisterRequest) => Promise<AuthSession>;
  refreshSession: (preferredWorkspaceId?: string | null) => Promise<CurrentUser>;
  switchWorkspace: (workspaceId: string) => Promise<CurrentUser>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);
const CURRENT_WORKSPACE_STORAGE_KEY = "surgepilot.currentWorkspaceId";

function readPreferredWorkspaceId() {
  if (typeof window === "undefined" || import.meta.env.MODE === "test") {
    return null;
  }
  return window.localStorage.getItem(CURRENT_WORKSPACE_STORAGE_KEY);
}

function persistPreferredWorkspaceId(workspaceId: string | null) {
  if (typeof window === "undefined" || import.meta.env.MODE === "test") {
    return;
  }
  if (workspaceId) {
    window.localStorage.setItem(CURRENT_WORKSPACE_STORAGE_KEY, workspaceId);
  } else {
    window.localStorage.removeItem(CURRENT_WORKSPACE_STORAGE_KEY);
  }
}

function sessionFromCurrentUser(currentUser: CurrentUser): SessionData {
  const legacyUser = currentUser as CurrentUser & Partial<SessionData>;
  const currentWorkspace =
    legacyUser.currentWorkspace ?? legacyUser.defaultWorkspace;
  const availableWorkspaces = legacyUser.availableWorkspaces ?? [
    {
      ...currentWorkspace,
      membership: { kind: "member" as const, joinedAt: null },
    },
  ];
  const permissions = legacyUser.permissions ?? {
    canManageWorkspaces: currentUser.user.role === "admin",
    canManageUsers: currentUser.user.role === "admin",
    canManageSystemSettings: currentUser.user.role === "admin",
    canViewSetupStatus: currentUser.user.role === "admin",
  };
  return {
    user: currentUser.user,
    currentWorkspace,
    defaultWorkspace: currentWorkspace,
    availableWorkspaces,
    permissions,
  };
}

export function AuthSessionProvider({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const [session, setSession] = useState<SessionData | null>(null);
  const [postLogoutRedirectPath, setPostLogoutRedirectPath] = useState<
    "/" | null
  >(null);

  useEffect(() => {
    let active = true;

    getCurrentUser(readPreferredWorkspaceId())
      .then((currentUser) => {
        if (active) {
          const nextSession = sessionFromCurrentUser(currentUser);
          setSession(nextSession);
          persistPreferredWorkspaceId(nextSession.currentWorkspace.id);
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.error(error);
        }
        if (active) {
          setSession(null);
          setCsrfToken(null);
          persistPreferredWorkspaceId(null);
        }
      })
      .finally(() => {
        if (active) {
          setIsRestoring(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (payload: LoginRequest) => {
    const response = await login(payload);
    const nextSession = sessionFromCurrentUser(response);
    setSession(nextSession);
    setPostLogoutRedirectPath(null);
    persistPreferredWorkspaceId(nextSession.currentWorkspace.id);
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const signUp = useCallback(async (payload: RegisterRequest) => {
    const response = await register(payload);
    const nextSession = sessionFromCurrentUser(response);
    setSession(nextSession);
    setPostLogoutRedirectPath(null);
    persistPreferredWorkspaceId(nextSession.currentWorkspace.id);
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const switchWorkspace = useCallback(
    async (workspaceId: string) => {
      const token = csrfToken ?? (await getCsrfToken()).csrfToken;
      const response = await switchWorkspaceRequest(workspaceId, token);
      const nextSession = sessionFromCurrentUser(response);
      setSession(nextSession);
      persistPreferredWorkspaceId(nextSession.currentWorkspace.id);
      setCsrfToken(token);
      return response;
    },
    [csrfToken],
  );

  const refreshSession = useCallback(async (preferredWorkspaceId?: string | null) => {
    const response = await getCurrentUser(preferredWorkspaceId ?? readPreferredWorkspaceId());
    const nextSession = sessionFromCurrentUser(response);
    setSession(nextSession);
    setPostLogoutRedirectPath(null);
    persistPreferredWorkspaceId(nextSession.currentWorkspace.id);
    return response;
  }, []);

  const clearPostLogoutRedirect = useCallback(() => {
    setPostLogoutRedirectPath(null);
  }, []);

  const signOut = useCallback(
    async (options?: { redirectPath?: "/" }) => {
      const token = csrfToken ?? (await getCsrfToken()).csrfToken;
      await logout(token);
      setPostLogoutRedirectPath(options?.redirectPath ?? null);
      setSession(null);
      setCsrfToken(null);
      persistPreferredWorkspaceId(null);
    },
    [csrfToken],
  );

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      csrfToken,
      isAuthenticated: session !== null,
      isRestoring,
      postLogoutRedirectPath,
      session,
      clearPostLogoutRedirect,
      signIn,
      signOut,
      signUp,
      refreshSession,
      switchWorkspace,
    }),
    [
      clearPostLogoutRedirect,
      csrfToken,
      isRestoring,
      postLogoutRedirectPath,
      refreshSession,
      session,
      signIn,
      signOut,
      signUp,
      switchWorkspace,
    ],
  );

  return (
    <AuthSessionContext.Provider value={value}>
      {children}
    </AuthSessionContext.Provider>
  );
}

export function useAuthSession() {
  const value = useContext(AuthSessionContext);
  if (value === null) {
    throw new Error("useAuthSession must be used inside AuthSessionProvider.");
  }
  return value;
}
