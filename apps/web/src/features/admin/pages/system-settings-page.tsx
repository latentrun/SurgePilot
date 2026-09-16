import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  ApiError,
  getCsrfToken,
  getLoadNodeConnectivitySummary,
  getSystemSettings,
  patchSystemSettings,
  type SystemSettingsPatchRequest,
  type SystemSettingsResponse,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { LoadNodeConnectivitySummaryCard } from "../../load-nodes/components/load-node-connectivity-summary";
import { AdminForbidden } from "../admin-access";

type Settings = SystemSettingsResponse["settings"];
type StatusItem = { label: string; configured: boolean };

type FormState = {
  allowSignup: boolean;
  loadSoftLimitWarningConcurrency: string;
  jmeterMemoryXmx: string;
  maxScenarioItemsPerTestPlan: string;
  maxSlaRulesPerTestPlan: string;
  maxRunDurationSeconds: string;
  maxRampUpSeconds: string;
  maxDelaySeconds: string;
  maxIterations: string;
  maxTargetRps: string;
  dependencyFileMaxBytes: string;
  dependencyFileAllowedExtensions: string;
  dependencyFilePreviewMaxBytes: string;
  dependencyFilePreviewBinaryDenyExtensions: string;
  loadNodeApiBaseUrl: string;
};

function errorCopy(error: unknown) {
  if (error instanceof ApiError) {
    return `Settings could not be saved. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Settings could not be saved. Refresh and try again.";
}

function extensionsToText(values: string[]) {
  return values.join(", ");
}

function normalizeExtensions(text: string) {
  const normalized: string[] = [];
  for (const part of text.split(/[\n,]+/)) {
    const value = part.trim().toLowerCase();
    if (!value) {
      continue;
    }
    const extension = value.startsWith(".") ? value : `.${value}`;
    if (!normalized.includes(extension)) {
      normalized.push(extension);
    }
  }
  return normalized;
}

function settingsToForm(settings: Settings): FormState {
  return {
    allowSignup: settings.allowSignup,
    loadSoftLimitWarningConcurrency: String(
      settings.loadSoftLimitWarningConcurrency,
    ),
    jmeterMemoryXmx: settings.jmeterMemoryXmx,
    maxScenarioItemsPerTestPlan: String(settings.maxScenarioItemsPerTestPlan),
    maxSlaRulesPerTestPlan: String(settings.maxSlaRulesPerTestPlan),
    maxRunDurationSeconds: String(settings.maxRunDurationSeconds),
    maxRampUpSeconds: String(settings.maxRampUpSeconds),
    maxDelaySeconds: String(settings.maxDelaySeconds),
    maxIterations: String(settings.maxIterations),
    maxTargetRps: String(settings.maxTargetRps),
    dependencyFileMaxBytes: String(settings.dependencyFileMaxBytes),
    dependencyFileAllowedExtensions: extensionsToText(
      settings.dependencyFileAllowedExtensions,
    ),
    dependencyFilePreviewMaxBytes: String(settings.dependencyFilePreviewMaxBytes),
    dependencyFilePreviewBinaryDenyExtensions: extensionsToText(
      settings.dependencyFilePreviewBinaryDenyExtensions,
    ),
    loadNodeApiBaseUrl: settings.loadNodeApiBaseUrl ?? "",
  };
}

function payloadFromForm(form: FormState): SystemSettingsPatchRequest {
  return {
    allowSignup: form.allowSignup,
    loadSoftLimitWarningConcurrency: Number(
      form.loadSoftLimitWarningConcurrency,
    ),
    jmeterMemoryXmx: form.jmeterMemoryXmx.trim(),
    maxScenarioItemsPerTestPlan: Number(form.maxScenarioItemsPerTestPlan),
    maxSlaRulesPerTestPlan: Number(form.maxSlaRulesPerTestPlan),
    maxRunDurationSeconds: Number(form.maxRunDurationSeconds),
    maxRampUpSeconds: Number(form.maxRampUpSeconds),
    maxDelaySeconds: Number(form.maxDelaySeconds),
    maxIterations: Number(form.maxIterations),
    maxTargetRps: Number(form.maxTargetRps),
    dependencyFileMaxBytes: Number(form.dependencyFileMaxBytes),
    dependencyFileAllowedExtensions: normalizeExtensions(
      form.dependencyFileAllowedExtensions,
    ),
    dependencyFilePreviewMaxBytes: Number(form.dependencyFilePreviewMaxBytes),
    dependencyFilePreviewBinaryDenyExtensions: normalizeExtensions(
      form.dependencyFilePreviewBinaryDenyExtensions,
    ),
    loadNodeApiBaseUrl: form.loadNodeApiBaseUrl.trim(),
  };
}

function defaultForm(): FormState {
  return {
    allowSignup: true,
    loadSoftLimitWarningConcurrency: "1000",
    jmeterMemoryXmx: "4G",
    maxScenarioItemsPerTestPlan: "20",
    maxSlaRulesPerTestPlan: "5",
    maxRunDurationSeconds: "86400",
    maxRampUpSeconds: "86400",
    maxDelaySeconds: "86400",
    maxIterations: "1000000",
    maxTargetRps: "100000",
    dependencyFileMaxBytes: "104857600",
    dependencyFileAllowedExtensions: "",
    dependencyFilePreviewMaxBytes: "65536",
    dependencyFilePreviewBinaryDenyExtensions: "",
    loadNodeApiBaseUrl: "",
  };
}

function SectionCard({
  children,
  description,
  eyebrow,
  title,
}: Readonly<{
  children: React.ReactNode;
  description: string;
  eyebrow: string;
  title: string;
}>) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_18px_50px_rgba(0,0,0,0.22)]">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">
        {eyebrow}
      </p>
      <h2 className="mt-2 text-lg font-semibold text-white">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
      <div className="mt-5 grid gap-4 md:grid-cols-2">{children}</div>
    </div>
  );
}

function NumberField({
  help,
  id,
  label,
  min,
  onChange,
  value,
}: Readonly<{
  help: string;
  id: string;
  label: string;
  min?: number;
  onChange: (value: string) => void;
  value: string;
}>) {
  return (
    <div className="block rounded-2xl border border-white/10 bg-black/15 p-4 text-sm text-white">
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      <input
        className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white outline-none ring-primary/30 transition focus:ring-2"
        id={id}
        min={min}
        onChange={(event) => onChange(event.target.value)}
        type="number"
        value={value}
      />
      <p className="mt-2 text-xs leading-5 text-text-muted">{help}</p>
    </div>
  );
}

function TextField({
  help,
  id,
  label,
  onChange,
  value,
}: Readonly<{
  help: string;
  id: string;
  label: string;
  onChange: (value: string) => void;
  value: string;
}>) {
  return (
    <div className="block rounded-2xl border border-white/10 bg-black/15 p-4 text-sm text-white">
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      <input
        className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white outline-none ring-primary/30 transition focus:ring-2"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
      <p className="mt-2 text-xs leading-5 text-text-muted">{help}</p>
    </div>
  );
}

function TextAreaField({
  help,
  id,
  label,
  onChange,
  value,
}: Readonly<{
  help: string;
  id: string;
  label: string;
  onChange: (value: string) => void;
  value: string;
}>) {
  return (
    <div className="block rounded-2xl border border-white/10 bg-black/15 p-4 text-sm text-white md:col-span-2">
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      <textarea
        className="mt-2 min-h-24 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white outline-none ring-primary/30 transition focus:ring-2"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
      <p className="mt-2 text-xs leading-5 text-text-muted">{help}</p>
    </div>
  );
}

function statusItems(data: SystemSettingsResponse | undefined): StatusItem[] {
  const status = data?.sensitiveStatus;
  return [
    {
      label: "Runner internal token",
      configured: status?.runnerInternalTokenConfigured === true,
    },
    {
      label: "SSH credential encryption key",
      configured: status?.sshCredentialEncryptionKeyConfigured === true,
    },
    {
      label: "MinIO credentials",
      configured: status?.minioCredentialsConfigured === true,
    },
  ];
}

export function AdminSystemSettingsPage() {
  const { csrfToken, session } = useAuthSession();
  const queryClient = useQueryClient();
  const isAdmin = session?.permissions.canManageSystemSettings === true;
  const query = useQuery({
    enabled: isAdmin,
    queryKey: ["admin-system-settings"],
    queryFn: getSystemSettings,
  });
  const connectivityQuery = useQuery({
    enabled: isAdmin,
    queryKey: ["load-node-connectivity-summary"],
    queryFn: getLoadNodeConnectivitySummary,
  });
  const [form, setForm] = useState<FormState>(() => defaultForm());
  useEffect(() => {
    if (query.data) {
      setForm(settingsToForm(query.data.settings));
    }
  }, [query.data]);
  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };
  const getWriteToken = async () => csrfToken ?? (await getCsrfToken()).csrfToken;
  const mutation = useMutation({
    mutationFn: async () =>
      patchSystemSettings(payloadFromForm(form), await getWriteToken()),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-system-settings"] }),
        queryClient.invalidateQueries({
          queryKey: ["load-node-connectivity-summary"],
        }),
      ]);
    },
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
          System Settings
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Edit only DB-backed runtime policies that apply immediately or to future
          new runs. Secrets, build-time values, stack settings, and hard limits
          remain deployment-managed.
        </p>
      </div>

      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        {query.isLoading ? (
          <p className="rounded-2xl border border-white/10 bg-white/[0.045] p-4 text-sm text-text-muted">
            Loading settings…
          </p>
        ) : null}

        <SectionCard
          description="Access changes apply immediately to non-bootstrap signup requests."
          eyebrow="Access"
          title="Signup policy"
        >
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-black/15 p-4 text-sm text-white md:col-span-2">
            <span>
              <label className="block font-medium" htmlFor="allow-signup">Allow local signup</label>
              <span className="mt-1 block text-xs leading-5 text-text-muted">
                Applies immediately. First administrator bootstrap stays available
                when no users exist.
              </span>
            </span>
            <input
              checked={form.allowSignup}
              id="allow-signup"
              className="h-5 w-5 accent-primary"
              onChange={(event) =>
                updateField("allowSignup", event.target.checked)
              }
              type="checkbox"
            />
          </div>
        </SectionCard>


        <SectionCard
          description="Configure the origin remote Load Nodes use for future runner callbacks."
          eyebrow="Load Node connectivity"
          title="Remote runner API origin"
        >
          <div className="md:col-span-2">
            <LoadNodeConnectivitySummaryCard
              isAdmin={isAdmin}
              loadFailed={connectivityQuery.isError}
              summary={connectivityQuery.data}
            />
          </div>
          <TextField
            help="Final origin remote Load Nodes use to call SurgePilot API. Do not include /api. Official Make startup derives the direct API origin from SURGEPILOT_API_HOST_PORT; set this value for multi-NIC, VPN, proxy, or remote deployments."
            id="load-node-api-base-url"
            label="Load Node API Base URL"
            onChange={(value) => updateField("loadNodeApiBaseUrl", value)}
            value={form.loadNodeApiBaseUrl}
          />
        </SectionCard>

        <SectionCard
          description="These values affect future create, edit, preview, and Run validation requests."
          eyebrow="Load guardrails"
          title="Test Plan policy limits"
        >
          <NumberField
            help="Applies immediately. Must stay below the deployment-managed hard limit."
            id="load-soft-limit-warning-concurrency"
            label="Load soft limit warning concurrency"
            min={1}
            onChange={(value) =>
              updateField("loadSoftLimitWarningConcurrency", value)
            }
            value={form.loadSoftLimitWarningConcurrency}
          />
          <NumberField
            help="Applies immediately to Test Plan save, preview, and Run validation."
            id="max-scenario-items-per-test-plan"
            label="Max Scenario items per Test Plan"
            min={1}
            onChange={(value) =>
              updateField("maxScenarioItemsPerTestPlan", value)
            }
            value={form.maxScenarioItemsPerTestPlan}
          />
          <NumberField
            help="Applies immediately to standard Run validation."
            id="max-sla-rules-per-test-plan"
            label="Max SLA rules per Test Plan"
            min={0}
            onChange={(value) => updateField("maxSlaRulesPerTestPlan", value)}
            value={form.maxSlaRulesPerTestPlan}
          />
          <NumberField
            help="Applies immediately. Existing Test Plans are not rewritten."
            id="max-run-duration-seconds"
            label="Max run duration seconds"
            min={60}
            onChange={(value) => updateField("maxRunDurationSeconds", value)}
            value={form.maxRunDurationSeconds}
          />
          <NumberField
            help="Applies immediately and must not exceed the duration limit."
            id="max-ramp-up-seconds"
            label="Max ramp-up seconds"
            min={0}
            onChange={(value) => updateField("maxRampUpSeconds", value)}
            value={form.maxRampUpSeconds}
          />
          <NumberField
            help="Applies immediately to load settings validation."
            id="max-delay-seconds"
            label="Max delay seconds"
            min={0}
            onChange={(value) => updateField("maxDelaySeconds", value)}
            value={form.maxDelaySeconds}
          />
          <NumberField
            help="Applies immediately to iteration-based load settings."
            id="max-iterations"
            label="Max iterations"
            min={1}
            onChange={(value) => updateField("maxIterations", value)}
            value={form.maxIterations}
          />
          <NumberField
            help="Applies immediately to throughput-based load settings."
            id="max-target-rps"
            label="Max target RPS"
            min={1}
            onChange={(value) => updateField("maxTargetRps", value)}
            value={form.maxTargetRps}
          />
        </SectionCard>

        <SectionCard
          description="This value is copied into future new Run snapshots. Existing runs and generated bundles are unchanged."
          eyebrow="JMeter runtime"
          title="Future Run heap setting"
        >
          <TextField
            help="Applies to future new runs only. Use uppercase K, M, or G, for example 4G."
            id="jmeter-memory-xmx"
            label="JMeter memory Xmx"
            onChange={(value) => updateField("jmeterMemoryXmx", value)}
            value={form.jmeterMemoryXmx}
          />
        </SectionCard>

        <SectionCard
          description="Upload changes apply to new uploads. Preview changes apply to future preview requests. Existing files are unchanged."
          eyebrow="Dependency files"
          title="Upload and preview policy"
        >
          <NumberField
            help="Applies immediately to the upload content-length gate and stored file size validation."
            id="dependency-file-max-bytes"
            label="Dependency file max bytes"
            min={1048576}
            onChange={(value) => updateField("dependencyFileMaxBytes", value)}
            value={form.dependencyFileMaxBytes}
          />
          <NumberField
            help="Applies immediately to preview reads. Existing files are unchanged."
            id="dependency-file-preview-max-bytes"
            label="Dependency file preview max bytes"
            min={1024}
            onChange={(value) =>
              updateField("dependencyFilePreviewMaxBytes", value)
            }
            value={form.dependencyFilePreviewMaxBytes}
          />
          <TextAreaField
            help="Comma or newline separated. Empty means uploads are unrestricted by extension."
            id="dependency-file-allowed-extensions"
            label="Dependency file allowed extensions"
            onChange={(value) =>
              updateField("dependencyFileAllowedExtensions", value)
            }
            value={form.dependencyFileAllowedExtensions}
          />
          <TextAreaField
            help="Comma or newline separated extensions that are never rendered as text previews."
            id="dependency-file-preview-binary-deny-extensions"
            label="Dependency file preview binary deny extensions"
            onChange={(value) =>
              updateField("dependencyFilePreviewBinaryDenyExtensions", value)
            }
            value={form.dependencyFilePreviewBinaryDenyExtensions}
          />
        </SectionCard>

        <SectionCard
          description="Read-only deployment status. Values show configured or missing only; secrets are never displayed or edited here."
          eyebrow="Read-only"
          title="Deployment status"
        >
          {statusItems(query.data).map((item) => (
            <div
              className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/15 p-4 text-sm text-white"
              key={item.label}
            >
              <span>{item.label}</span>
              <span
                className={
                  item.configured
                    ? "rounded-full border border-success/30 bg-success-container px-3 py-1 text-xs font-semibold text-on-success-container"
                    : "rounded-full border border-warning/30 bg-warning-container px-3 py-1 text-xs font-semibold text-on-warning-container"
                }
              >
                {item.configured ? "Configured" : "Missing"}
              </span>
            </div>
          ))}
        </SectionCard>

        <div className="flex items-center justify-end gap-3 rounded-3xl border border-white/10 bg-white/[0.045] p-5">
          {mutation.isSuccess ? (
            <p className="text-sm text-success">Settings saved.</p>
          ) : null}
          <button
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60"
            disabled={mutation.isPending || query.isLoading}
            type="submit"
          >
            Save Settings
          </button>
        </div>
      </form>

      {mutation.isError ? (
        <div className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {errorCopy(mutation.error)}
        </div>
      ) : null}
    </section>
  );
}
