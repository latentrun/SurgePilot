import { useEffect, useState } from "react";

import { AuthSessionProvider, useAuthSession } from "./app/auth-session";
import { LoginPage } from "./features/auth/pages/login-page";
import { RegisterPage } from "./features/auth/pages/register-page";

function LoadingPage() {
  return <main><p>Loading SurgePilot…</p></main>;
}

function OverviewPage() {
  const { session, signOut } = useAuthSession();

  async function handleLogout() {
    try {
      await signOut();
      window.history.replaceState({}, "", "/login");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch {
      // Keep the authenticated view visible if the server could not complete logout.
    }
  }

  if (!session) return null;
  return (
    <main>
      <p>Overview</p>
      <h1>Welcome to SurgePilot</h1>
      <p>Signed in as {session.user.displayName} ({session.user.email}).</p>
      <p>Workspace: {session.defaultWorkspace.name}</p>
      <button onClick={() => void handleLogout()} type="button">Sign out</button>
    </main>
  );
}

function AppRoutes() {
  const { isAuthenticated, isRestoring } = useAuthSession();
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (isRestoring) return <LoadingPage />;
  if (!isAuthenticated) return pathname === "/register" ? <RegisterPage /> : <LoginPage />;
  return <OverviewPage />;
}

export function App() {
  return <AuthSessionProvider><AppRoutes /></AuthSessionProvider>;
}
