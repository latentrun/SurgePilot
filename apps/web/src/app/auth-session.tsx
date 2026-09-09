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
  getCsrfToken,
  getCurrentUser,
  login,
  logout,
  register,
  switchWorkspace as switchWorkspaceRequest,
  type AuthSession,
  type CurrentUser,
  type LoginRequest,
  type RegisterRequest,
} from "./api-client";

type SessionData = Pick<CurrentUser, "user" | "defaultWorkspace"> & {
  currentWorkspace: NonNullable<CurrentUser["currentWorkspace"]>;
  availableWorkspaces: NonNullable<CurrentUser["availableWorkspaces"]>;
  permissions: NonNullable<CurrentUser["permissions"]>;
};

type AuthSessionContextValue = {
  csrfToken: string | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  session: SessionData | null;
  signIn: (payload: LoginRequest) => Promise<AuthSession>;
  signOut: () => Promise<void>;
  signUp: (payload: RegisterRequest) => Promise<AuthSession>;
  switchWorkspace: (workspaceId: string) => Promise<CurrentUser>;
  refreshSession: (preferredWorkspaceId?: string | null) => Promise<CurrentUser>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);
const WORKSPACE_KEY = "surgepilot.currentWorkspaceId";

function preferredWorkspaceId() {
  return typeof window === "undefined" ? null : window.localStorage.getItem(WORKSPACE_KEY);
}

function persistWorkspace(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(WORKSPACE_KEY, id);
  else window.localStorage.removeItem(WORKSPACE_KEY);
}

function sessionFromResponse(response: CurrentUser): SessionData {
  const currentWorkspace = response.currentWorkspace ?? response.defaultWorkspace;
  return {
    user: response.user,
    defaultWorkspace: currentWorkspace,
    currentWorkspace,
    availableWorkspaces: response.availableWorkspaces ?? [
      { ...currentWorkspace, membership: { kind: "member", joinedAt: null } },
    ],
    permissions: response.permissions ?? {
      canManageWorkspaces: response.user.role === "admin",
      canManageUsers: response.user.role === "admin",
      canManageSystemSettings: response.user.role === "admin",
      canViewSetupStatus: response.user.role === "admin",
    },
  };
}

export function AuthSessionProvider({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const [session, setSession] = useState<SessionData | null>(null);

  useEffect(() => {
    let active = true;

    getCurrentUser(preferredWorkspaceId())
      .then((currentUser) => {
        if (active) {
          const next = sessionFromResponse(currentUser);
          setSession(next);
          persistWorkspace(next.currentWorkspace.id);
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.error(error);
        }
        if (active) {
          setSession(null);
          setCsrfToken(null);
          persistWorkspace(null);
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
    const next = sessionFromResponse(response);
    setSession(next);
    persistWorkspace(next.currentWorkspace.id);
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const signUp = useCallback(async (payload: RegisterRequest) => {
    const response = await register(payload);
    const next = sessionFromResponse(response);
    setSession(next);
    persistWorkspace(next.currentWorkspace.id);
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const refreshSession = useCallback(async (preferred?: string | null) => {
    const response = await getCurrentUser(preferred ?? preferredWorkspaceId());
    const next = sessionFromResponse(response);
    setSession(next);
    persistWorkspace(next.currentWorkspace.id);
    return response;
  }, []);

  const switchWorkspace = useCallback(async (workspaceId: string) => {
    const token = csrfToken ?? (await getCsrfToken()).csrfToken;
    const response = await switchWorkspaceRequest(workspaceId, token);
    const next = sessionFromResponse(response);
    setSession(next);
    setCsrfToken(token);
    persistWorkspace(next.currentWorkspace.id);
    return response;
  }, [csrfToken]);

  const signOut = useCallback(async () => {
    const token = csrfToken ?? (await getCsrfToken()).csrfToken;
    await logout(token);
    setSession(null);
    setCsrfToken(null);
    persistWorkspace(null);
  }, [csrfToken]);

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      csrfToken,
      isAuthenticated: session !== null,
      isRestoring,
      refreshSession,
      session,
      signIn,
      signOut,
      signUp,
      switchWorkspace,
    }),
    [csrfToken, isRestoring, refreshSession, session, signIn, signOut, signUp, switchWorkspace],
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
