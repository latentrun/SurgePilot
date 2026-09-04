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
  type AuthSession,
  type CurrentUser,
  type LoginRequest,
  type RegisterRequest,
} from "./api-client";

type SessionData = Pick<CurrentUser, "user" | "defaultWorkspace">;

type AuthSessionContextValue = {
  csrfToken: string | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  session: SessionData | null;
  refreshSession: () => Promise<CurrentUser>;
  signIn: (payload: LoginRequest) => Promise<AuthSession>;
  signOut: () => Promise<void>;
  signUp: (payload: RegisterRequest) => Promise<AuthSession>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

function sessionFromResponse(response: CurrentUser): SessionData {
  return {
    user: response.user,
    defaultWorkspace: response.defaultWorkspace,
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

    getCurrentUser()
      .then((currentUser) => {
        if (active) {
          setSession(sessionFromResponse(currentUser));
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.error(error);
        }
        if (active) {
          setSession(null);
          setCsrfToken(null);
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
    setSession(sessionFromResponse(response));
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const signUp = useCallback(async (payload: RegisterRequest) => {
    const response = await register(payload);
    setSession(sessionFromResponse(response));
    setCsrfToken(response.csrfToken);
    return response;
  }, []);

  const refreshSession = useCallback(async () => {
    const response = await getCurrentUser();
    setSession(sessionFromResponse(response));
    return response;
  }, []);

  const signOut = useCallback(async () => {
    const token = csrfToken ?? (await getCsrfToken()).csrfToken;
    await logout(token);
    setSession(null);
    setCsrfToken(null);
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
    }),
    [csrfToken, isRestoring, refreshSession, session, signIn, signOut, signUp],
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
