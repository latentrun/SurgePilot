import { useQuery } from "@tanstack/react-query";

import { ApiError, getAdminSetupStatus } from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

function StatusBadge({ ok, label }: Readonly<{ ok: boolean; label: string }>) {
  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[11px] leading-4",
        ok
          ? "border-success/30 bg-success/10 text-success"
          : "border-warning/35 bg-warning/10 text-warning",
      ].join(" ")}
    >
      <span
        className={
          ok
            ? "h-2 w-2 rounded-full bg-success"
            : "h-2 w-2 rounded-full bg-warning"
        }
      />
      {label}
    </span>
  );
}

function StatusCard({
  title,
  ok,
  okLabel,
  missingLabel,
}: Readonly<{
  title: string;
  ok: boolean;
  okLabel: string;
  missingLabel: string;
}>) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
        {title}
      </div>
      <div className="mt-3">
        <StatusBadge ok={ok} label={ok ? okLabel : missingLabel} />
      </div>
    </div>
  );
}

function runtimeStatusLabel(status: string | null | undefined) {
  if (status === "ready") return "Ready";
  if (status === "artifact_missing") return "Artifact missing";
  return "Not configured";
}

function errorCopy(error: unknown) {
  if (error instanceof ApiError) {
    return `Setup Status could not be loaded. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Setup Status could not be loaded. Refresh and try again.";
}

export function AdminSetupStatusPage() {
  const { session } = useAuthSession();
  const isAdmin = session?.user.role === "admin";
  const query = useQuery({
    enabled: isAdmin,
    queryKey: ["admin-setup-status"],
    queryFn: getAdminSetupStatus,
    retry: false,
  });

  if (!isAdmin) {
    return <AdminForbidden />;
  }

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="surgepilot-glass rounded-3xl p-7">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">
          Admin
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-white">
          Setup Status
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Read-only platform readiness checks for the P0 workspace flow.
          Sensitive configuration values are never shown here.
        </p>
      </div>

      <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
        {query.isLoading ? (
          <div className="p-5 text-text-muted">Loading setup status…</div>
        ) : null}
        {query.isError ? (
          <div className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
            {errorCopy(query.error)}
          </div>
        ) : null}
        {query.data ? (
          <div className="grid gap-4 md:grid-cols-2">
            <StatusCard
              title="Default Workspace"
              ok={query.data.hasDefaultWorkspace}
              okLabel="Available"
              missingLabel="Missing"
            />
            <StatusCard
              title="Artifact Storage"
              ok={query.data.storageAvailable}
              okLabel="Available"
              missingLabel="Unavailable"
            />
            <StatusCard
              title="SSH Credential Encryption"
              ok={
                query.data.sensitiveStatus
                  ?.sshCredentialEncryptionKeyConfigured === true
              }
              okLabel="Configured"
              missingLabel="Missing"
            />
            <StatusCard
              title="Load Node Runtime"
              ok={query.data.loadNodeRuntimeStatus === "ready"}
              okLabel="Ready"
              missingLabel={runtimeStatusLabel(query.data.loadNodeRuntimeStatus)}
            />
            <StatusCard
              title="Local Signup"
              ok={query.data.allowSignup}
              okLabel="Enabled"
              missingLabel="Disabled"
            />
            <StatusCard
              title="Bootstrap"
              ok={!query.data.needsBootstrap}
              okLabel="Completed"
              missingLabel="Administrator required"
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
