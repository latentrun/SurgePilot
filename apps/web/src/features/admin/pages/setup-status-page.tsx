import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getAdminSetupStatus,
  type SetupStatus,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return `Setup Status could not be loaded. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Setup Status could not be loaded. Refresh and try again.";
}

function StatusCard({
  label,
  missingLabel,
  ok,
  okLabel,
}: Readonly<{
  label: string;
  missingLabel: string;
  ok: boolean;
  okLabel: string;
}>) {
  return (
    <div>
      <div>{label}</div>
      <div>{ok ? okLabel : missingLabel}</div>
    </div>
  );
}

export function AdminSetupStatusPage() {
  const { session } = useAuthSession();
  const isAdmin = session?.user.role === "admin";
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAdmin) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await getAdminSetupStatus();
      setStatus(data);
    } catch (error) {
      setStatus(null);
      setLoadError(errorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isAdmin) {
    return <AdminForbidden />;
  }

  return (
    <main>
      <section>
        <p>Admin</p>
        <h1>Setup Status</h1>
        <p>
          Read-only platform readiness checks for the P0 workspace flow.
          Sensitive configuration values are never shown here.
        </p>
      </section>

      {isLoading ? (
        <section aria-label="Loading setup status" role="status">
          Loading setup status…
        </section>
      ) : null}

      {loadError ? (
        <section role="alert">
          <p>{loadError}</p>
          <button onClick={() => void load()} type="button">
            Try again
          </button>
        </section>
      ) : null}

      {status ? (
        <section>
          <div>
            <StatusCard
              label="Default Workspace"
              missingLabel="Missing"
              ok={status.hasDefaultWorkspace}
              okLabel="Available"
            />
            <StatusCard
              label="Local Signup"
              missingLabel="Disabled"
              ok={status.allowSignup}
              okLabel="Enabled"
            />
            <StatusCard
              label="Bootstrap"
              missingLabel="Administrator required"
              ok={!status.needsBootstrap}
              okLabel="Completed"
            />
          </div>
        </section>
      ) : null}
    </main>
  );
}
