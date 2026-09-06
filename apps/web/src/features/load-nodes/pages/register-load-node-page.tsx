import { useMemo, useState } from "react";

import {
  createLoadNode,
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

function cn(...inputs: (string | boolean | null | undefined)[]) {
  return inputs.filter(Boolean).join(" ");
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

async function copyText(text: string): Promise<{
  ok: boolean;
  reason?: string;
}> {
  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch {
    return { ok: false, reason: "Clipboard access is unavailable." };
  }
}

function navigateToLoadNodes() {
  window.history.replaceState({}, "", "/resources/load-nodes");
  window.dispatchEvent(new PopStateEvent("popstate"));
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
  if (!form.host.trim()) {
    errors.host = "Host is required.";
  }
  if (form.sshPort < 1 || form.sshPort > 65535) {
    errors.sshPort = "Port must be between 1 and 65535.";
  }
  if (!form.sshUser.trim()) {
    errors.sshUser = "SSH user is required.";
  }
  if (form.runnerHome && !form.runnerHome.trim().startsWith("/")) {
    errors.runnerHome = "Runner home must be an absolute path.";
  }
  if (form.scope === "public" && role !== "admin") {
    errors.scope = "Only Admin can register Public nodes.";
  }
  if (form.authType === "password" && !form.password) {
    errors.password = "Password is required.";
  }
  if (form.authType === "private_key" && !form.privateKey) {
    errors.privateKey = "SSH private key is required.";
  }
  if (!trustedHostKey) {
    errors.sshHostKey = "Scan and confirm the SSH host key.";
  }
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

function CheckCircle2({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M21.801 10A10 10 0 1 1 17 3.335" />
      <path d="m9 11 3 3L22 4" />
    </svg>
  );
}

function KeyRound({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
      <circle cx="16.5" cy="7.5" r="0.5" fill="currentColor" />
    </svg>
  );
}

function ShieldCheck({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function Copy({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <rect height="13" rx="2" ry="2" width="13" x="9" y="9" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export function RegisterLoadNodePage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const role = session?.user.role;
  const isAdmin = role === "admin";

  const [form, setForm] = useState<FormState>(defaultForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [created, setCreated] = useState<LoadNodeDetail | null>(null);
  const [trustedHostKey, setTrustedHostKey] =
    useState<LoadNodeSshHostKeyScanResponse | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  if (session === null) {
    return null;
  }

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
    setCopyFeedback(result.ok ? "Copied." : result.reason ?? "Copy failed.");
  }

  async function handleScan() {
    if (!form.host.trim()) return;
    setIsScanning(true);
    setApiError(null);
    try {
      const token = await getWriteToken();
      const result = await scanLoadNodeSshHostKey(
        { scope: form.scope, host: form.host, sshPort: form.sshPort },
        workspaceId,
        token,
      );
      setTrustedHostKey(result);
      setErrors((current) => ({ ...current, sshHostKey: "" }));
    } catch (error) {
      setTrustedHostKey(null);
      setApiError(loadNodeErrorMessage(error));
    } finally {
      setIsScanning(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate(form, role, trustedHostKey);
    setErrors(nextErrors);
    setApiError(null);
    if (Object.values(nextErrors).some(Boolean)) {
      return;
    }
    setIsSubmitting(true);
    try {
      const token = await getWriteToken();
      const node = await createLoadNode(
        toPayload(form, trustedHostKey as LoadNodeSshHostKeyScanResponse),
        workspaceId,
        token,
      );
      if (node.authType === "generated_key") {
        setCreated(node);
      } else {
        navigateToLoadNodes();
      }
    } catch (error) {
      setApiError(loadNodeErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (created) {
    return (
      <div className="mx-auto flex max-w-container-max flex-col gap-8">
        <section className="surgepilot-glass rounded-2xl p-8">
          <div className="flex items-center gap-3 text-success">
            <CheckCircle2 className="h-7 w-7" />
            <h1 className="font-display text-[28px] font-semibold leading-9 text-white">
              Load Node Registered
            </h1>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted">
            Add this public key to the target host before initializing the node.
            The private key is encrypted and never displayed. Before
            initializing, confirm the host meets the target requirements listed
            on the registration form.
          </p>
          <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
                Installation key
              </span>
              <button
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!created.generatedPublicKey}
                onClick={() => void handleCopy(created.generatedPublicKey ?? "")}
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
            <a
              className="inline-flex items-center rounded-lg bg-primary px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary"
              href="/resources/load-nodes"
            >
              Back to Load Nodes
            </a>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-8">
      <div>
        <h1 className="font-display text-[34px] font-semibold leading-10 text-white">
          Register Load Node
        </h1>
        <p className="mt-2 max-w-3xl text-base leading-6 text-text-muted">
          Enter the SSH connection details and credentials. You can initialize
          the node after registration.
        </p>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <form
          className="surgepilot-glass grid gap-5 rounded-2xl p-6 sm:grid-cols-2"
          onSubmit={(event) => void handleSubmit(event)}
        >
          {apiError ? (
            <div className="rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container sm:col-span-2">
              {apiError}
            </div>
          ) : null}

          <Field label="Scope" error={errors.scope}>
            <select
              className={cn(inputClass(Boolean(errors.scope)), "text-text-main")}
              onChange={(event) =>
                update("scope", event.target.value as LoadNodeScope)
              }
              value={form.scope}
            >
              <option value="workspace">Private</option>
              <option disabled={!isAdmin} value="public">
                Public
              </option>
            </select>
          </Field>
          <Field label="Host/IP" error={errors.host}>
            <input
              className={cn(inputClass(Boolean(errors.host)), "text-text-main")}
              onChange={(event) => update("host", event.target.value)}
              placeholder="10.0.2.15"
              value={form.host}
            />
          </Field>
          <Field label="Port" error={errors.sshPort}>
            <input
              className={cn(
                inputClass(Boolean(errors.sshPort)),
                "text-text-main",
              )}
              onChange={(event) =>
                update("sshPort", Number(event.target.value))
              }
              type="number"
              value={form.sshPort}
            />
          </Field>
          <Field label="SSH user" error={errors.sshUser}>
            <input
              className={cn(inputClass(Boolean(errors.sshUser)), "text-text-main")}
              onChange={(event) => update("sshUser", event.target.value)}
              value={form.sshUser}
            />
          </Field>

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
                className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-sm font-semibold text-primary transition hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isScanning || !form.host.trim()}
                onClick={() => void handleScan()}
                type="button"
              >
                <KeyRound className="h-4 w-4" />
                {isScanning ? "Scanning..." : "Scan key"}
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

          <Field label="Runner home" error={errors.runnerHome}>
            <input
              className={cn(
                inputClass(Boolean(errors.runnerHome)),
                "text-text-main",
              )}
              onChange={(event) => update("runnerHome", event.target.value)}
              placeholder="Use API default"
              value={form.runnerHome}
            />
          </Field>
          <Field label="Maintainer">
            <input
              className={cn(inputClass(false), "text-text-main")}
              onChange={(event) => update("maintainer", event.target.value)}
              value={form.maintainer}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Remark">
              <input
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) => update("remark", event.target.value)}
                value={form.remark}
              />
            </Field>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:col-span-2">
            <div className="mb-4 flex items-center gap-2 text-white">
              <KeyRound className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">SSH credentials</h2>
            </div>
            <Field label="Authentication method">
              <select
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) =>
                  update("authType", event.target.value as LoadNodeAuthType)
                }
                value={form.authType}
              >
                <option value="password">Password</option>
                <option value="private_key">SSH private key</option>
                <option value="generated_key">Generate keypair</option>
              </select>
            </Field>
            {form.authType === "password" ? (
              <div className="mt-3">
                <Field label="Password" error={errors.password}>
                  <input
                    autoComplete="new-password"
                    className={cn(
                      inputClass(Boolean(errors.password)),
                      "text-text-main",
                    )}
                    onChange={(event) =>
                      update("password", event.target.value)
                    }
                    type="password"
                    value={form.password}
                  />
                </Field>
              </div>
            ) : null}
            {form.authType === "private_key" ? (
              <>
                <div className="mt-3">
                  <Field label="SSH private key" error={errors.privateKey}>
                    <textarea
                      className={cn(
                        inputClass(Boolean(errors.privateKey)),
                        "min-h-32 resize-y py-3 font-mono text-xs text-text-main",
                      )}
                      onChange={(event) =>
                        update("privateKey", event.target.value)
                      }
                      value={form.privateKey}
                    />
                  </Field>
                </div>
                <div className="mt-3">
                  <Field label="Private key passphrase (optional)">
                    <input
                      autoComplete="new-password"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        update("privateKeyPassphrase", event.target.value)
                      }
                      type="password"
                      value={form.privateKeyPassphrase}
                    />
                  </Field>
                </div>
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
            <a
              className="inline-flex items-center rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
              href="/resources/load-nodes"
            >
              Cancel
            </a>
            <button
              className="inline-flex h-11 items-center justify-center rounded-lg bg-primary px-5 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting ? "Registering..." : "Register Load Node"}
            </button>
          </div>
        </form>

        <aside className="surgepilot-glass grid gap-6 rounded-2xl p-6">
          <div>
            <div className="mb-4 flex items-center gap-2 text-white">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Requirements</h2>
            </div>
            <ul className="grid gap-3">
              {HOST_REQUIREMENTS.map((requirement) => (
                <li
                  className="flex items-start gap-2 text-sm text-text-main"
                  key={requirement.label}
                >
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  <span>
                    <span className="font-semibold">
                      {requirement.label}:
                    </span>{" "}
                    {requirement.value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-primary">
                Verify on host
              </span>
              <button
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:text-white"
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
        </aside>
      </div>
    </div>
  );
}

function inputClass(hasError: boolean) {
  return cn(
    "h-10 w-full rounded-lg border bg-surface-container px-3 text-sm outline-none transition focus:border-primary/50",
    hasError ? "border-error/60" : "border-white/10",
  );
}

function Field({
  children,
  error,
  label,
}: Readonly<{ children: React.ReactNode; error?: string; label: string }>) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-text-main">
        {label}
      </span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-error">{error}</span>
      ) : null}
    </label>
  );
}
