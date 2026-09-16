import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, KeyRound, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import {
  createLoadNode,
  getLoadNodeConnectivitySummary,
  getCsrfToken,
  scanLoadNodeSshHostKey,
  type LoadNodeAuthType,
  type LoadNodeCreateRequest,
  type LoadNodeDetail,
  type LoadNodeScope,
  type LoadNodeSshHostKeyScanResponse,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { copyText } from "../../../utils/clipboard";
import { LoadNodeConnectivitySummaryCard } from "../components/load-node-connectivity-summary";
import { loadNodeErrorMessage } from "./load-node-copy";

type FormState = {
  authType: LoadNodeAuthType;
  host: string;
  maintainer: string;
  password: string;
  privateKey: string;
  privateKeyPassphrase: string;
  remark: string;
  runnerHome: string;
  scope: LoadNodeScope;
  sshPort: number;
  sshUser: string;
};

const defaultForm: FormState = {
  authType: "password",
  host: "",
  maintainer: "",
  password: "",
  privateKey: "",
  privateKeyPassphrase: "",
  remark: "",
  runnerHome: "",
  scope: "workspace",
  sshPort: 22,
  sshUser: "surgepilot",
};

const HOST_REQUIREMENTS: { label: string; value: string }[] = [
  { label: "OS", value: "Ubuntu 24.04+ or Debian 12+" },
  { label: "CPU", value: "x86_64 (amd64) or aarch64 (arm64)" },
  { label: "Access", value: "SSH reachable from the SurgePilot API" },
  { label: "Dependencies", value: "tar and a POSIX shell" },
  { label: "Base runtime", value: "Java 11+ and python3 3.12+" },
];

const HOST_VERIFY_COMMAND =
  'uname -m && (. /etc/os-release; echo "$PRETTY_NAME") && java -version && python3 --version && tar --version';

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function toPayload(
  form: FormState,
  trustedHostKey: LoadNodeSshHostKeyScanResponse,
): LoadNodeCreateRequest {
  const base = {
    scope: form.scope,
    host: form.host,
    sshPort: form.sshPort,
    sshUser: form.sshUser,
    sshHostKey: {
      algorithm: trustedHostKey.algorithm,
      publicKey: trustedHostKey.publicKey,
      fingerprintSha256: trustedHostKey.fingerprintSha256,
    },
    maintainer: form.maintainer || undefined,
    remark: form.remark || undefined,
  };
  const runnerHome = form.runnerHome.trim();
  const baseWithOptionalRunnerHome = runnerHome
    ? { ...base, runnerHome }
    : base;
  if (form.authType === "password") {
    return {
      ...baseWithOptionalRunnerHome,
      credential: { authType: "password", password: form.password },
    } as LoadNodeCreateRequest;
  }
  if (form.authType === "private_key") {
    return {
      ...baseWithOptionalRunnerHome,
      credential: {
        authType: "private_key",
        privateKey: form.privateKey,
        privateKeyPassphrase: form.privateKeyPassphrase || undefined,
      },
    } as LoadNodeCreateRequest;
  }
  return {
    ...baseWithOptionalRunnerHome,
    credential: { authType: "generated_key" },
  } as LoadNodeCreateRequest;
}

function validate(
  form: FormState,
  role: string | undefined,
  trustedHostKey: LoadNodeSshHostKeyScanResponse | null,
) {
  const errors: Record<string, string> = {};
  if (!form.host.trim()) errors.host = "Host is required.";
  if (form.sshPort < 1 || form.sshPort > 65535)
    errors.sshPort = "Port must be between 1 and 65535.";
  if (!form.sshUser.trim()) errors.sshUser = "SSH user is required.";
  if (form.runnerHome && !form.runnerHome.startsWith("/"))
    errors.runnerHome = "Runner home must be an absolute path.";
  if (form.scope === "public" && role !== "admin")
    errors.scope = "Only Admin can register Public nodes.";
  if (form.authType === "password" && !form.password)
    errors.password = "Password is required.";
  if (form.authType === "private_key" && !form.privateKey)
    errors.privateKey = "SSH private key is required.";
  if (!trustedHostKey) errors.sshHostKey = "Scan and confirm the SSH host key.";
  return errors;
}

function formHasDraft(form: FormState) {
  return (
    form.host.trim() !== "" ||
    form.maintainer.trim() !== "" ||
    form.password !== "" ||
    form.privateKey !== "" ||
    form.privateKeyPassphrase !== "" ||
    form.remark.trim() !== "" ||
    form.runnerHome.trim() !== "" ||
    form.authType !== defaultForm.authType ||
    form.scope !== defaultForm.scope ||
    form.sshPort !== defaultForm.sshPort ||
    form.sshUser !== defaultForm.sshUser
  );
}

export function RegisterLoadNodePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [form, setForm] = useState<FormState>(defaultForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [created, setCreated] = useState<LoadNodeDetail | null>(null);
  const [trustedHostKey, setTrustedHostKey] =
    useState<LoadNodeSshHostKeyScanResponse | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const role = session?.user.role;
  const isAdmin = role === "admin";
  const connectivityQuery = useQuery({
    enabled: session !== null,
    queryKey: ["load-node-connectivity-summary"],
    queryFn: getLoadNodeConnectivitySummary,
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      createLoadNode(
        toPayload(form, trustedHostKey as LoadNodeSshHostKeyScanResponse),
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: async (node) => {
      await queryClient.invalidateQueries({
        queryKey: ["load-nodes", workspaceId],
      });
      setApiError(null);
      setCopyFeedback(null);
      if (node.authType === "generated_key") {
        setCreated(node);
      } else {
        navigate("/resources/load-nodes");
      }
    },
    onError: (error) => setApiError(loadNodeErrorMessage(error)),
  });

  const scanMutation = useMutation({
    mutationFn: async () =>
      scanLoadNodeSshHostKey(
        { scope: form.scope, host: form.host, sshPort: form.sshPort },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (result) => {
      setTrustedHostKey(result);
      setErrors((current) => ({ ...current, sshHostKey: "" }));
      setApiError(null);
    },
    onError: (error) => {
      setTrustedHostKey(null);
      setApiError(loadNodeErrorMessage(error));
    },
  });

  const workspaceSwitchGuard = useMemo(
    () => ({
      dirty: created === null && formHasDraft(form),
      safePath: "/resources/load-nodes",
      onAbandon: () => {
        setForm(defaultForm);
        setTrustedHostKey(null);
        setErrors({});
        setApiError(null);
        setCopyFeedback(null);
      },
    }),
    [created, form],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);

  if (session === null) return null;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    if (key === "host" || key === "sshPort") {
      setTrustedHostKey(null);
    }
    setErrors((current) => ({ ...current, [key]: "" }));
  }

  async function handleCopy(text: string) {
    setCopyFeedback(null);
    const result = await copyText(text);
    setCopyFeedback(result.ok ? "Copied." : result.reason);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate(form, role, trustedHostKey);
    setErrors(nextErrors);
    setApiError(null);
    if (Object.values(nextErrors).some(Boolean)) return;
    try {
      await createMutation.mutateAsync();
    } catch {
      // mutation owns visible API error
    }
  }

  if (created) {
    return (
      <section className="mx-auto max-w-3xl">
        <div className="surgepilot-glass rounded-3xl p-8">
          <div className="flex items-center gap-3 text-success">
            <CheckCircle2 className="h-7 w-7" />
            <h1 className="font-display text-2xl font-semibold text-white">
              Load Node Registered
            </h1>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            Add this public key to the target host before initializing the node.
            The private key is encrypted and never displayed.
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Before initializing, confirm the host meets the target requirements:
            Ubuntu 24.04+ or Debian 12+, x86_64 or aarch64, Java 11+, and
            python3 3.12+.
          </p>
          <div className="mt-6">
            <LoadNodeConnectivitySummaryCard
              isAdmin={isAdmin}
              loadFailed={connectivityQuery.isError}
              successContext
              summary={connectivityQuery.data}
            />
          </div>
          <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
                Installation key
              </span>
              <button
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!created.generatedPublicKey}
                onClick={() =>
                  void handleCopy(created.generatedPublicKey ?? "")
                }
                type="button"
              >
                <Copy className="h-3 w-3" />
                Copy
              </button>
            </div>
            {copyFeedback ? (
              <p className="mb-2 text-xs text-text-muted">{copyFeedback}</p>
            ) : null}
            <pre className="whitespace-pre-wrap break-all font-mono text-xs text-text-main">
              {created.generatedPublicKey}
            </pre>
          </div>
          <div className="mt-6 flex gap-3">
            <Link
              className="rounded-lg border border-white/10 px-4 py-2 text-white"
              to="/resources/load-nodes"
            >
              Back to Load Nodes
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-semibold text-white">
          Register Load Node
        </h1>
        <p className="mt-2 text-sm text-text-muted">
          Enter the SSH connection details and credentials. You can initialize
          the node after registration.
        </p>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <form
          className="surgepilot-glass grid gap-5 rounded-3xl p-6 sm:grid-cols-2"
          onSubmit={(event) => void submit(event)}
        >
          {apiError ? (
            <div className="rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container sm:col-span-2">
              {apiError}
            </div>
          ) : null}
          <label className="grid gap-1 text-sm text-text-muted">
            Scope
            <select
              className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
              value={form.scope}
              onChange={(e) => update("scope", e.target.value as LoadNodeScope)}
            >
              <option value="workspace">Private</option>
              <option disabled={role !== "admin"} value="public">
                Public
              </option>
            </select>
            {errors.scope ? (
              <span className="text-error">{errors.scope}</span>
            ) : null}
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            Host/IP
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={form.host}
              onChange={(e) => update("host", e.target.value)}
            />
            {errors.host ? (
              <span className="text-error">{errors.host}</span>
            ) : null}
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            Port
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              type="number"
              value={form.sshPort}
              onChange={(e) => update("sshPort", Number(e.target.value))}
            />
            {errors.sshPort ? (
              <span className="text-error">{errors.sshPort}</span>
            ) : null}
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            SSH user
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={form.sshUser}
              onChange={(e) => update("sshUser", e.target.value)}
            />
            {errors.sshUser ? (
              <span className="text-error">{errors.sshUser}</span>
            ) : null}
          </label>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:col-span-2">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-white">
                  SSH host key trust
                </div>
                <p className="mt-1 text-xs text-text-muted">
                  Scan the target host from SurgePilot, verify the fingerprint,
                  then register the node with the confirmed key.
                </p>
              </div>
              <button
                className="rounded-lg border border-primary/30 px-3 py-2 text-sm font-semibold text-primary disabled:cursor-not-allowed disabled:opacity-50"
                disabled={scanMutation.isPending || !form.host.trim()}
                onClick={() => void scanMutation.mutateAsync()}
                type="button"
              >
                {scanMutation.isPending ? "Scanning..." : "Scan key"}
              </button>
            </div>
            {errors.sshHostKey ? (
              <p className="mb-3 text-sm text-error">{errors.sshHostKey}</p>
            ) : null}
            {trustedHostKey ? (
              <div className="rounded-xl border border-success/25 bg-success/10 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-success">
                  Trusted for {trustedHostKey.host}:{trustedHostKey.sshPort}
                </div>
                <dl className="mt-3 grid gap-2 text-xs text-text-main">
                  <div>
                    <dt className="text-text-muted">Algorithm</dt>
                    <dd className="font-mono">{trustedHostKey.algorithm}</dd>
                  </div>
                  <div>
                    <dt className="text-text-muted">SHA256 fingerprint</dt>
                    <dd className="break-all font-mono">
                      {trustedHostKey.fingerprintSha256}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-text-muted">known_hosts line</dt>
                    <dd className="break-all font-mono">
                      {trustedHostKey.knownHostsLine}
                    </dd>
                  </div>
                </dl>
              </div>
            ) : (
              <p className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-text-muted">
                No host key is trusted yet. Host or port changes clear the
                confirmation.
              </p>
            )}
          </div>
          <label className="grid gap-1 text-sm text-text-muted sm:col-span-2">
            Runner home
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              placeholder="Use API default"
              value={form.runnerHome}
              onChange={(e) => update("runnerHome", e.target.value)}
            />
            {errors.runnerHome ? (
              <span className="text-error">{errors.runnerHome}</span>
            ) : null}
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            Maintainer
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={form.maintainer}
              onChange={(e) => update("maintainer", e.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            Remark
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={form.remark}
              onChange={(e) => update("remark", e.target.value)}
            />
          </label>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:col-span-2">
            <div className="mb-4 flex items-center gap-2 text-white">
              <KeyRound className="h-4 w-4 text-primary" />
              SSH credentials
            </div>
            <label className="grid gap-1 text-sm text-text-muted">
              Authentication method
              <select
                className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
                value={form.authType}
                onChange={(e) =>
                  update("authType", e.target.value as LoadNodeAuthType)
                }
              >
                <option value="password">Password</option>
                <option value="private_key">SSH private key</option>
                <option value="generated_key">Generate keypair</option>
              </select>
            </label>
            {form.authType === "password" ? (
              <label className="mt-3 grid gap-1 text-sm text-text-muted">
                Password
                <input
                  className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                  type="password"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                />
                {errors.password ? (
                  <span className="text-error">{errors.password}</span>
                ) : null}
              </label>
            ) : null}
            {form.authType === "private_key" ? (
              <>
                <label className="mt-3 grid gap-1 text-sm text-text-muted">
                  SSH private key
                  <textarea
                    className="min-h-32 rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs text-white"
                    value={form.privateKey}
                    onChange={(e) => update("privateKey", e.target.value)}
                  />
                  {errors.privateKey ? (
                    <span className="text-error">{errors.privateKey}</span>
                  ) : null}
                </label>
                <label className="mt-3 grid gap-1 text-sm text-text-muted">
                  Private key passphrase (optional)
                  <input
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                    type="password"
                    value={form.privateKeyPassphrase}
                    onChange={(e) =>
                      update("privateKeyPassphrase", e.target.value)
                    }
                  />
                </label>
              </>
            ) : null}
            {form.authType === "generated_key" ? (
              <p className="mt-3 rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
                SurgePilot will generate a key pair and display only the public
                key after registration.
              </p>
            ) : null}
          </div>
          <div className="flex justify-end gap-3 sm:col-span-2">
            <Link
              className="rounded-lg border border-white/10 px-4 py-2 text-white"
              to="/resources/load-nodes"
            >
              Cancel
            </Link>
            <button
              className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary"
              disabled={createMutation.isPending}
              type="submit"
            >
              Register Load Node
            </button>
          </div>
        </form>
        <aside className="grid gap-6">
          <LoadNodeConnectivitySummaryCard
            isAdmin={isAdmin}
            loadFailed={connectivityQuery.isError}
            summary={connectivityQuery.data}
          />
          <div className="surgepilot-glass rounded-3xl p-6">
            <div className="mb-4 flex items-center gap-2 text-white">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Requirements</h2>
            </div>
            <ul className="grid gap-3">
              {HOST_REQUIREMENTS.map((requirement) => (
                <li
                  key={requirement.label}
                  className="flex items-start gap-2 text-sm text-text-main"
                >
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  <span>
                    <span className="font-semibold">{requirement.label}:</span>{" "}
                    {requirement.value}
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/30 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-primary">
                  Verify on host
                </span>
                <button
                  className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted"
                  onClick={() => void handleCopy(HOST_VERIFY_COMMAND)}
                  type="button"
                >
                  <Copy className="h-3 w-3" />
                  Copy
                </button>
              </div>
              {copyFeedback ? (
                <p className="mb-2 text-xs text-text-muted">{copyFeedback}</p>
              ) : null}
              <pre className="whitespace-pre-wrap break-all font-mono text-xs text-text-main">
                {HOST_VERIFY_COMMAND}
              </pre>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
