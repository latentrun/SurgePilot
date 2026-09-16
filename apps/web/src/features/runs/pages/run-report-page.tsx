import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { z } from "zod";

import {
  downloadDebugHttpBodyBlob,
  getCsrfToken,
  getRunMonitoringLink,
  getRunReport,
  listRunArtifacts,
  patchRunValidity,
  stopRun,
  type RunArtifactItem,
  type RunMonitoringLinkResponse,
  type RunReportDetail,
  type RunValidity,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { copyText } from "../../../utils/clipboard";
import {
  SectionCard,
  StatusPill,
  activeRunStates,
  formatDate,
  formatDuration,
  formatEnum,
  formatMs,
  formatNumber,
  formatPercent,
} from "./run-shared";

type DebugHttpTrace = NonNullable<RunReportDetail["debugHttpTrace"]>;
type DebugHttpTraceEntry = NonNullable<DebugHttpTrace["entries"]>[number];
type DebugHttpTraceBody = DebugHttpTraceEntry["requestBody"];

const stringArraySchema = z.array(z.string());
const nullableStringSchema = z.string().nullable().optional();
const nullableNumberSchema = z.number().nullable().optional();
const dateTimeSchema = z.iso.datetime({ offset: true });
const nullableDateTimeSchema = dateTimeSchema.nullable().optional();
const reportRowSchema = z
  .object({
    label: nullableStringSchema,
    totalRequests: nullableNumberSchema,
    successRequests: nullableNumberSchema,
    failedRequests: nullableNumberSchema,
    errorRate: nullableNumberSchema,
    averageResponseTimeMs: nullableNumberSchema,
    p90Ms: nullableNumberSchema,
    p95Ms: nullableNumberSchema,
    p99Ms: nullableNumberSchema,
    responseCodeCounts: z.record(z.string(), z.number()).optional(),
  })
  .passthrough();
const debugTraceBodySchema = z
  .object({
    bodyStorage: z.string(),
    bodyTruncated: z.boolean(),
    contentType: nullableStringSchema,
    downloadArtifactId: nullableStringSchema,
    dropReason: nullableStringSchema,
    inlinePreview: nullableStringSchema,
    sha256Prefix: nullableStringSchema,
    sizeBytes: nullableNumberSchema,
    text: nullableStringSchema,
  })
  .passthrough();
const debugTraceEntrySchema = z
  .object({
    sequence: z.number(),
    method: z.string(),
    url: z.string(),
    label: nullableStringSchema,
    durationMs: nullableNumberSchema,
    responseStatus: nullableNumberSchema,
    error: nullableStringSchema,
    requestHeaders: z.record(z.string(), z.string()).optional(),
    responseHeaders: z.record(z.string(), z.string()).optional(),
    requestBody: debugTraceBodySchema,
    responseBody: debugTraceBodySchema,
  })
  .passthrough();
const loadSettingsSchema = z
  .object({
    concurrencyPerNode: nullableNumberSchema,
    rampUpSeconds: nullableNumberSchema,
    holdForSeconds: nullableNumberSchema,
    iterations: nullableNumberSchema,
    targetRps: nullableNumberSchema,
    steps: nullableNumberSchema,
    delaySeconds: nullableNumberSchema,
  })
  .passthrough();
const snapshotSlaRuleSchema = z
  .object({
    metric: nullableStringSchema,
    condition: nullableStringSchema,
    thresholdText: nullableStringSchema,
  })
  .passthrough();
const resourceRequestSchema = z
  .object({
    mode: nullableStringSchema,
    poolType: nullableStringSchema,
    selectedNodeId: nullableStringSchema,
    selectedNodeIds: stringArraySchema.optional(),
    nodeCount: nullableNumberSchema,
    expectedConcurrencyPerNode: nullableNumberSchema,
  })
  .passthrough();

const runReportEnvelopeSchema = z
  .object({
    id: z.string(),
    verdict: z
      .object({
        state: z.string(),
        runType: z.string(),
        sourceType: z.string(),
        validity: z.string(),
        slaResult: z.string(),
        slaResultReason: nullableStringSchema,
        durationMs: nullableNumberSchema,
        triggeredBy: z.object({ email: z.string() }).passthrough(),
        createdAt: dateTimeSchema,
        startedAt: nullableDateTimeSchema,
        endedAt: nullableDateTimeSchema,
        lastHeartbeatAt: nullableDateTimeSchema,
        failureReason: nullableStringSchema,
        forcedConvergence: z.boolean(),
      })
      .passthrough(),
    kpiSummary: z
      .object({
        status: z.string(),
        missingReasons: stringArraySchema.optional(),
        totalRequests: nullableNumberSchema,
        failedRequests: nullableNumberSchema,
        errorRate: nullableNumberSchema,
        averageResponseTimeMs: nullableNumberSchema,
        p90Ms: nullableNumberSchema,
        p95Ms: nullableNumberSchema,
        p99Ms: nullableNumberSchema,
      })
      .passthrough(),
    failureDiagnostics: z
      .object({
        failureReason: nullableStringSchema,
        notes: stringArraySchema.optional(),
      })
      .passthrough(),
    finalStatsPreview: z
      .object({
        status: z.string(),
        rows: z.array(reportRowSchema),
        truncated: z.boolean(),
        warnings: stringArraySchema.optional(),
      })
      .passthrough(),
    debugHttpTrace: z.union([
      z.null(),
      z
        .object({
          status: z.string(),
          entryCount: z.number(),
          traceTruncated: z.boolean(),
          warnings: stringArraySchema.optional(),
          entries: z.array(debugTraceEntrySchema).optional(),
        })
        .passthrough(),
    ]),
    snapshot: z
      .object({
        scenarioCount: z.number(),
        slaRuleCount: z.number(),
        dependencyFileCount: z.number(),
        sourceName: nullableStringSchema,
        sourceRevision: nullableNumberSchema,
        envGroupName: nullableStringSchema,
        runMode: nullableStringSchema,
        scenarioItems: z
          .array(
            z
              .object({
                scenarioName: z.string(),
                loadSettings: loadSettingsSchema,
              })
              .passthrough(),
          )
          .optional(),
        scenarioNames: stringArraySchema.optional(),
        slaRules: z.array(snapshotSlaRuleSchema).optional(),
        dependencyFileNames: stringArraySchema.optional(),
        envGroupVariableKeys: stringArraySchema.optional(),
        resourceRequest: z.union([z.null(), resourceRequestSchema]).optional(),
      })
      .passthrough(),
    allocatedNodes: z.array(
      z
        .object({
          id: z.string(),
          name: z.string(),
          scope: z.string(),
          state: z.string(),
          nodeIndex: z.number(),
          totalNodes: z.number(),
          lastHeartbeatAt: nullableDateTimeSchema,
          terminalReason: nullableStringSchema,
          cleanupStatus: nullableStringSchema,
          quarantineReason: nullableStringSchema,
          slaResult: nullableStringSchema,
        })
        .passthrough(),
    ),
    artifactsSummary: z
      .object({
        count: z.number(),
        hasArtifactsZip: z.boolean(),
        hasFinalStatsCsv: z.boolean(),
      })
      .passthrough(),
  })
  .passthrough();

async function loadRunReport(runId: string, workspaceId: string) {
  const report = await getRunReport(runId, workspaceId);
  const parsed = runReportEnvelopeSchema.safeParse(report);
  if (!parsed.success) {
    throw new Error("Invalid Run Report response.");
  }
  return parsed.data as RunReportDetail;
}

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function verdictTone(value: string) {
  if (value === "finished" || value === "passed" || value === "valid")
    return "success" as const;
  if (value === "failed" || value === "invalid") return "error" as const;
  if (value === "aborted" || value === "not_evaluated")
    return "warning" as const;
  return "primary" as const;
}

function slaLabel(value: string) {
  if (value === "passed") return "SLA passed";
  if (value === "failed") return "SLA failed";
  return "SLA not evaluated";
}

function slaResultReasonLabel(value: string | null | undefined) {
  if (value === "missing_sla_result")
    return "One or more Load Nodes did not report an SLA result.";
  if (value === "node_sla_failed")
    return "At least one Load Node reported an SLA failure.";
  return null;
}

const runFailureDetails: Record<string, { label: string; message: string }> = {
  allocation_failed: {
    label: "Allocation failed",
    message: "One or more Load Node allocations failed.",
  },
  bundle_invalid: {
    label: "Execution bundle invalid",
    message: "The execution bundle could not be loaded by the Runner.",
  },
  heartbeat_timeout: {
    label: "Heartbeat timeout",
    message: "Runner heartbeat timed out.",
  },
  runner_accept_timeout: {
    label: "Runner acceptance timeout",
    message: "The Runner did not accept the Run before the timeout.",
  },
  runner_exit_nonzero: {
    label: "Runner execution failed",
    message: "The Runner process exited before completing successfully.",
  },
  runner_start_failed: {
    label: "Runner start failed",
    message: "The Runner could not start the execution.",
  },
  runner_start_timeout: {
    label: "Runner start timeout",
    message: "The Runner did not start before the timeout.",
  },
  unknown_runner_error: {
    label: "Runner execution failed",
    message: "The Runner reported an unexpected execution failure.",
  },
  stale_process_detected: {
    label: "Stale process detected",
    message: "The Load Node must be cleaned up before another Run can start.",
  },
  stop_grace_timeout: {
    label: "Stop timeout",
    message: "The Run did not stop within the allowed grace period.",
  },
};

function runFailureDetail(value: string | null | undefined) {
  return value ? runFailureDetails[value] : undefined;
}

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs text-text-muted">{hint}</p> : null}
    </div>
  );
}

export function runReportRefetchInterval(
  report: RunReportDetail | undefined,
  summaryPolls: number,
) {
  if (!report) return false;
  if (activeRunStates.has(report.verdict.state)) return 5000;
  if (report.kpiSummary.status === "pending" && summaryPolls < 12) return 5000;
  return false;
}

function VerdictSummary({ report }: { report: RunReportDetail }) {
  const verdict = report.verdict;
  const slaReason = slaResultReasonLabel(verdict.slaResultReason);
  const failure = runFailureDetail(verdict.failureReason);
  return (
    <SectionCard title="Verdict Summary">
      <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="flex flex-wrap gap-2">
          <StatusPill tone={verdictTone(verdict.state)}>
            {formatEnum(verdict.state)}
          </StatusPill>
          <StatusPill tone="primary">{formatEnum(verdict.runType)}</StatusPill>
          <StatusPill tone={verdictTone(verdict.slaResult)}>
            {slaLabel(verdict.slaResult)}
          </StatusPill>
          <StatusPill tone={verdictTone(verdict.validity)}>
            {formatEnum(verdict.validity)}
          </StatusPill>
        </div>
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
          <div>
            <dt className="text-secondary">Status</dt>
            <dd className="font-semibold text-white">
              {formatEnum(verdict.state)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Duration</dt>
            <dd className="font-semibold text-white">
              {formatDuration(verdict.durationMs)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Triggered by</dt>
            <dd className="font-semibold text-white">
              {verdict.triggeredBy.email}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Created</dt>
            <dd className="font-semibold text-white">
              {formatDate(verdict.createdAt)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Started</dt>
            <dd className="font-semibold text-white">
              {formatDate(verdict.startedAt)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Ended</dt>
            <dd className="font-semibold text-white">
              {formatDate(verdict.endedAt)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Last heartbeat</dt>
            <dd className="font-semibold text-white">
              {formatDate(verdict.lastHeartbeatAt)}
            </dd>
          </div>
          <div>
            <dt className="text-secondary">Forced convergence</dt>
            <dd className="font-semibold text-white">
              {verdict.forcedConvergence ? "Yes" : "No"}
            </dd>
          </div>
        </dl>
        {activeRunStates.has(verdict.state) ? (
          <p className="mt-4 rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
            Run is still active. Static run metadata will refresh every 5
            seconds.
          </p>
        ) : null}
        {failure ? (
          <p className="mt-4 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
            {failure.message}
          </p>
        ) : null}
        {slaReason ? (
          <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
            {slaReason}
          </p>
        ) : null}
      </div>
    </SectionCard>
  );
}

function KpiSummary({ report }: { report: RunReportDetail }) {
  const kpi = report.kpiSummary;
  const reason = kpi.missingReasons?.length
    ? `Reason: ${kpi.missingReasons.map(formatEnum).join(", ")}`
    : undefined;
  return (
    <SectionCard title="KPI Summary">
      {kpi.status !== "parsed" ? (
        <p className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
          {kpi.status === "missing"
            ? "Final stats artifact has not been uploaded yet."
            : "Summary not yet ready."}
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Total Requests"
          value={formatNumber(kpi.totalRequests)}
          hint={reason}
        />
        <KpiCard
          label="Failed Requests"
          value={formatNumber(kpi.failedRequests)}
        />
        <KpiCard label="Error Rate" value={formatPercent(kpi.errorRate)} />
        <KpiCard
          label="Average Response Time"
          value={formatMs(kpi.averageResponseTimeMs)}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <KpiCard label="P90" value={formatMs(kpi.p90Ms)} />
        <KpiCard label="P95" value={formatMs(kpi.p95Ms)} />
        <KpiCard label="P99" value={formatMs(kpi.p99Ms)} />
      </div>
    </SectionCard>
  );
}

function MonitoringSection({
  link,
  isLoading,
}: {
  link: RunMonitoringLinkResponse | undefined;
  isLoading: boolean;
}) {
  const status = link?.status;
  const isDebugDisabled = link?.disabledReason === "debug_run_not_monitored";
  return (
    <SectionCard title="Monitoring">
      {isLoading ? (
        <p className="text-sm text-text-muted">Loading monitoring link…</p>
      ) : null}
      {!isLoading && !link ? (
        <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
          Monitoring details are unavailable for this run.
        </p>
      ) : null}
      {link?.enabledForRun && link.platformMonitoringUrl ? (
        <div className="rounded-2xl border border-success/30 bg-success/10 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <StatusPill tone="success">Enabled</StatusPill>
              <p className="mt-3 text-sm text-text-main">
                Grafana dashboard is available for this Standard Run.
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Window: {link.grafanaFrom ?? "N/A"} → {link.grafanaTo ?? "N/A"}
              </p>
            </div>
            <Link
              className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
              to={link.platformMonitoringUrl}
            >
              Open Monitoring
            </Link>
          </div>
        </div>
      ) : null}
      {link && !link.enabledForRun ? (
        <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          <StatusPill tone="warning">{formatEnum(status)}</StatusPill>
          <p className="mt-3">
            {isDebugDisabled
              ? "Debug Runs do not emit monitoring data."
              : "Monitoring is not configured for this run."}
          </p>
          {link.warnings?.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {link.warnings.map((warning) => (
                <StatusPill key={warning} tone="warning">
                  {formatEnum(warning)}
                </StatusPill>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </SectionCard>
  );
}

function FailureDiagnostics({ report }: { report: RunReportDetail }) {
  const diagnostics = report.failureDiagnostics;
  const notes = diagnostics.notes ?? [];
  const failure = runFailureDetail(diagnostics.failureReason);
  const hasDetails = Boolean(failure || notes.length);
  if (!hasDetails) return null;
  return (
    <SectionCard title="Failure Diagnostics">
      <div className="space-y-3 text-sm">
        {failure ? (
          <p>
            <span className="text-secondary">Reason:</span>{" "}
            <span className="text-white">{failure.label}</span>
          </p>
        ) : null}
        {failure ? (
          <p className="rounded-xl border border-error/30 bg-error-container p-3 text-on-error-container">
            {failure.message}
          </p>
        ) : null}
        {notes.length ? (
          <div className="flex flex-wrap gap-2">
            {notes.map((note) => (
              <StatusPill key={note} tone="warning">
                {formatEnum(note)}
              </StatusPill>
            ))}
          </div>
        ) : null}
        <p className="text-text-muted">
          Download logs or the archive from Artifacts for deeper
          troubleshooting.
        </p>
      </div>
    </SectionCard>
  );
}

function HeaderLines({ headers }: { headers: Record<string, string> }) {
  const lines = Object.entries(headers ?? {});
  if (!lines.length)
    return <p className="text-xs text-text-muted">No headers captured.</p>;
  return (
    <pre className="mt-2 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs leading-5 text-text-main">
      {lines.map(([key, value]) => `${key}: ${value}`).join("\n")}
    </pre>
  );
}

async function copyDebugTraceText(
  text: string,
  setFeedback: (message: string | null) => void,
) {
  setFeedback(null);
  const result = await copyText(text);
  setFeedback(result.ok ? "Copied." : result.reason);
}

function BodyBlock({
  title,
  body,
  runId,
  workspaceId,
}: {
  title: string;
  body: DebugHttpTraceBody;
  runId: string;
  workspaceId: string;
}) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const bodyState =
    body.bodyStorage ?? (body.bodyTruncated ? "truncated" : "inline");
  const preview = body.inlinePreview ?? body.text ?? null;
  const metadata = [
    body.contentType,
    body.sizeBytes != null ? `${body.sizeBytes} B` : null,
    body.sha256Prefix ? `sha256:${body.sha256Prefix}` : null,
    `storage:${bodyState}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const canDownloadSidecar =
    bodyState === "sidecar" && Boolean(body.downloadArtifactId);
  const downloadSidecar = async () => {
    if (!body.downloadArtifactId) return;
    setIsDownloading(true);
    setDownloadError(null);
    try {
      const blob = await downloadDebugHttpBodyBlob(
        runId,
        body.downloadArtifactId,
        workspaceId,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `debug-http-body-${body.downloadArtifactId}.bin`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("Sidecar body download failed.");
    } finally {
      setIsDownloading(false);
    }
  };
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
          {title}
        </p>
        {preview ? (
          <button
            className="text-xs text-primary disabled:text-text-muted"
            disabled={!preview}
            onClick={() => void copyDebugTraceText(preview, setCopyFeedback)}
            type="button"
          >
            Copy preview
          </button>
        ) : null}
      </div>
      {metadata ? (
        <p className="mt-1 text-xs text-text-muted">{metadata}</p>
      ) : null}
      {copyFeedback ? (
        <p className="mt-1 text-xs text-text-muted">{copyFeedback}</p>
      ) : null}
      {preview ? (
        <pre className="mt-2 max-h-72 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs leading-5 text-text-main">
          {preview}
        </pre>
      ) : (
        <p className="mt-2 text-xs text-text-muted">
          No inline body preview captured.
        </p>
      )}
      {bodyState === "sidecar" ? (
        <div className="mt-2 rounded-xl border border-primary/20 bg-primary/10 p-3 text-xs text-text-main">
          <p>Large sanitized body stored as an internal sidecar artifact.</p>
          {canDownloadSidecar ? (
            <button
              className="mt-2 inline-flex text-primary disabled:text-text-muted"
              disabled={isDownloading}
              onClick={() => void downloadSidecar()}
              type="button"
            >
              {isDownloading
                ? "Downloading sanitized body…"
                : "Download sanitized body"}
            </button>
          ) : (
            <p className="mt-2 text-warning">Sidecar body is unavailable.</p>
          )}
          {downloadError ? (
            <p className="mt-2 text-warning">{downloadError}</p>
          ) : null}
        </div>
      ) : null}
      {bodyState === "dropped" ? (
        <p className="mt-2 text-xs text-warning">
          Body was not captured: {formatEnum(body.dropReason ?? "body_dropped")}
          .
        </p>
      ) : null}
      {body.bodyTruncated && bodyState !== "sidecar" ? (
        <p className="mt-2 text-xs text-warning">
          Body preview truncated to the debug trace limit.
        </p>
      ) : null}
    </div>
  );
}

function HttpTraceEntryCard({
  entry,
  runId,
  workspaceId,
}: {
  entry: DebugHttpTraceEntry;
  runId: string;
  workspaceId: string;
}) {
  const entryRunId = runId;
  const [expanded, setExpanded] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="grid gap-3 text-sm md:grid-cols-[0.4fr_1.8fr_0.4fr_0.5fr] md:items-center">
        <StatusPill tone="primary">{entry.method}</StatusPill>
        <div>
          <p className="break-all font-semibold text-white">{entry.url}</p>
          {entry.label ? (
            <p className="mt-1 text-xs text-text-muted">{entry.label}</p>
          ) : null}
          <button
            className="mt-2 text-xs text-primary disabled:text-text-muted"
            disabled={!entry.url}
            onClick={() => void copyDebugTraceText(entry.url, setCopyFeedback)}
            type="button"
          >
            Copy URL
          </button>
        </div>
        {copyFeedback ? (
          <p className="text-xs text-text-muted">{copyFeedback}</p>
        ) : null}
        <StatusPill
          tone={(entry.responseStatus ?? 0) >= 400 ? "error" : "success"}
        >
          {entry.responseStatus ?? "N/A"}
        </StatusPill>
        <span className="font-mono text-xs text-text-muted">
          {formatMs(entry.durationMs)}
        </span>
      </div>
      <button
        className="mt-3 text-xs text-primary"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        {expanded ? "Hide trace details" : "Show trace details"}
      </button>
      {expanded ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="font-semibold text-white">Request</p>
            <HeaderLines headers={entry.requestHeaders ?? {}} />
            <div className="mt-4">
              <BodyBlock
                title="Request body"
                body={entry.requestBody}
                runId={entryRunId}
                workspaceId={workspaceId}
              />
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="font-semibold text-white">Response</p>
            <HeaderLines headers={entry.responseHeaders ?? {}} />
            <div className="mt-4">
              <BodyBlock
                title="Response body"
                body={entry.responseBody}
                runId={entryRunId}
                workspaceId={workspaceId}
              />
            </div>
            {entry.error ? (
              <div className="mt-3 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
                <p>{entry.error}</p>
                <button
                  className="mt-2 text-xs text-primary disabled:text-text-muted"
                  disabled={!entry.error}
                  onClick={() => void copyDebugTraceText(entry.error ?? "", setCopyFeedback)}
                  type="button"
                >
                  Copy error
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function HttpTraceSection({
  report,
  workspaceId,
}: {
  report: RunReportDetail;
  workspaceId: string;
}) {
  const trace = report.debugHttpTrace;
  const supportsHttpTrace =
    report.verdict.runType === "debug" &&
    (report.verdict.sourceType === "debug_scenario" ||
      report.verdict.sourceType === "test_plan");
  if (!supportsHttpTrace) return null;
  if (!trace) {
    if (!activeRunStates.has(report.verdict.state)) return null;
    return (
      <SectionCard title="HTTP Trace">
        <p className="text-sm text-text-muted">
          HTTP trace details will appear after the Debug Run uploads its
          request/response artifact.
        </p>
      </SectionCard>
    );
  }
  if (trace.status !== "available") {
    return (
      <SectionCard title="HTTP Trace">
        <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
          HTTP trace is unavailable for this Debug Run.
        </p>
        {trace.warnings?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {trace.warnings.map((warning) => (
              <StatusPill key={warning} tone="warning">
                {formatEnum(warning)}
              </StatusPill>
            ))}
          </div>
        ) : null}
        <p className="mt-3 text-sm text-text-muted">
          Download available artifacts and logs for deeper troubleshooting.
        </p>
      </SectionCard>
    );
  }
  const entries = trace.entries ?? [];
  return (
    <SectionCard title="HTTP Trace">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusPill tone="primary">{trace.entryCount} requests</StatusPill>
        {trace.traceTruncated ? (
          <StatusPill tone="warning">Trace truncated</StatusPill>
        ) : null}
        {trace.warnings?.map((warning) => (
          <StatusPill key={warning} tone="warning">
            {formatEnum(warning)}
          </StatusPill>
        ))}
      </div>
      {entries.length === 0 ? (
        <p className="text-sm text-text-muted">
          No HTTP request entries were captured.
        </p>
      ) : null}
      <div className="space-y-3">
        {entries.map((entry, index) => (
          <HttpTraceEntryCard
            entry={entry}
            key={`${entry.sequence}-${entry.url}-${index}`}
            runId={report.id}
            workspaceId={workspaceId}
          />
        ))}
      </div>
    </SectionCard>
  );
}

function FinalStatsPreview({ report }: { report: RunReportDetail }) {
  const preview = report.finalStatsPreview;
  return (
    <SectionCard title="Final Stats Preview">
      {preview.status === "missing" ? (
        <p className="text-sm text-text-muted">
          No final stats rows are available yet.
        </p>
      ) : null}
      {preview.status === "pending" ? (
        <p className="text-sm text-text-muted">Summary is pending.</p>
      ) : null}
      {preview.status === "failed" ? (
        <p className="text-sm text-warning">
          Final stats summary is unavailable. Raw artifacts can still be
          downloaded.
        </p>
      ) : null}
      {preview.warnings?.length ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {preview.warnings.map((warning) => (
            <StatusPill key={warning} tone="warning">
              {formatEnum(warning)}
            </StatusPill>
          ))}
        </div>
      ) : null}
      {preview.status === "parsed" ? (
        <div className="overflow-x-auto">
          {preview.truncated ? (
            <p className="mb-3 text-xs text-warning">
              Preview truncated to the safe P0 row limit.
            </p>
          ) : null}
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
              <tr>
                <th className="py-2">Label</th>
                <th>Total</th>
                <th>Failed</th>
                <th>Error Rate</th>
                <th>Avg RT</th>
                <th>P95</th>
                <th>Codes</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, index) => (
                <tr
                  className="border-t border-white/10"
                  key={`${row.label ?? "total"}-${index}`}
                >
                  <td className="py-3 text-white">{row.label ?? "Total"}</td>
                  <td>{formatNumber(row.totalRequests)}</td>
                  <td>{formatNumber(row.failedRequests)}</td>
                  <td>{formatPercent(row.errorRate)}</td>
                  <td>{formatMs(row.averageResponseTimeMs)}</td>
                  <td>{formatMs(row.p95Ms)}</td>
                  <td className="font-mono text-xs text-text-muted">
                    {Object.entries(row.responseCodeCounts ?? {})
                      .map(([code, count]) => `${code}: ${count}`)
                      .join(", ") || "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </SectionCard>
  );
}

function secondsLabel(value: number | null | undefined) {
  return value === null || value === undefined ? "N/A" : `${value}s`;
}

function numberLabel(value: number | null | undefined) {
  return value === null || value === undefined ? "N/A" : formatNumber(value);
}

function SnapshotScenarioCard({
  item,
}: {
  item: NonNullable<RunReportDetail["snapshot"]["scenarioItems"]>[number];
}) {
  const settings = item.loadSettings;
  const entries = [
    ["Concurrency", numberLabel(settings.concurrencyPerNode)],
    ["Ramp up", secondsLabel(settings.rampUpSeconds)],
    ["Hold", secondsLabel(settings.holdForSeconds)],
    ["Iterations", numberLabel(settings.iterations)],
    ["Target RPS", numberLabel(settings.targetRps)],
    ["Steps", numberLabel(settings.steps)],
    ["Delay", secondsLabel(settings.delaySeconds)],
  ];
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <p className="font-semibold text-white">{item.scenarioName}</p>
      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([label, value]) => (
          <div key={label}>
            <dt className="text-secondary">{label}</dt>
            <dd className="font-semibold text-white">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function SnapshotSummary({ report }: { report: RunReportDetail }) {
  const snapshot = report.snapshot;
  return (
    <SectionCard title="Snapshot Summary">
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-secondary">Source</dt>
          <dd className="font-semibold text-white">
            {snapshot.sourceName ?? "N/A"}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Revision</dt>
          <dd className="font-semibold text-white">
            {snapshot.sourceRevision ?? "N/A"}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Environment</dt>
          <dd className="font-semibold text-white">
            {snapshot.envGroupName ?? "N/A"}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Run mode</dt>
          <dd className="font-semibold text-white">
            {formatEnum(snapshot.runMode)}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Scenarios</dt>
          <dd className="font-semibold text-white">{snapshot.scenarioCount}</dd>
        </div>
        <div>
          <dt className="text-secondary">SLA rules</dt>
          <dd className="font-semibold text-white">{snapshot.slaRuleCount}</dd>
        </div>
        <div>
          <dt className="text-secondary">Dependency files</dt>
          <dd className="font-semibold text-white">
            {snapshot.dependencyFileCount}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Node mode</dt>
          <dd className="font-semibold text-white">
            {formatEnum(snapshot.resourceRequest?.mode)}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Expected concurrency</dt>
          <dd className="font-semibold text-white">
            {snapshot.resourceRequest?.expectedConcurrencyPerNode ?? "N/A"}
          </dd>
        </div>
      </dl>
      {snapshot.scenarioNames?.length ? (
        <p className="mt-4 text-sm text-text-muted">
          Scenarios: {snapshot.scenarioNames.join(", ")}
        </p>
      ) : null}
      {snapshot.scenarioItems?.length ? (
        <div className="mt-5 space-y-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
            Scenario load settings
          </p>
          {snapshot.scenarioItems.map((item) => (
            <SnapshotScenarioCard item={item} key={item.scenarioName} />
          ))}
        </div>
      ) : null}
      {snapshot.slaRules?.length ? (
        <div className="mt-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
            SLA rules
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {snapshot.slaRules.map((rule, index) => (
              <StatusPill
                key={`${rule.metric ?? "metric"}-${index}`}
                tone="warning"
              >
                {[rule.metric, rule.condition, rule.thresholdText]
                  .filter(Boolean)
                  .join(" ")}
              </StatusPill>
            ))}
          </div>
        </div>
      ) : null}
      {snapshot.dependencyFileNames?.length ? (
        <div className="mt-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
            Dependency files
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {snapshot.dependencyFileNames.map((name) => (
              <StatusPill key={name} tone="primary">
                {name}
              </StatusPill>
            ))}
          </div>
        </div>
      ) : null}
      {snapshot.envGroupVariableKeys?.length ? (
        <div className="mt-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
            Environment variable keys
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {snapshot.envGroupVariableKeys.map((key) => (
              <StatusPill key={key} tone="primary">
                {key}
              </StatusPill>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-muted">
            Values are intentionally hidden in the report.
          </p>
        </div>
      ) : null}
    </SectionCard>
  );
}

function artifactLabel(type: string) {
  if (type === "artifacts_zip") return "Archive bundle";
  if (type === "final_stats_csv") return "Final stats CSV";
  if (type === "taurus_log") return "Taurus log";
  if (type === "jmeter_log") return "JMeter log";
  return "Run log";
}

function artifactOwnerLabel(item: RunArtifactItem, report: RunReportDetail) {
  const node = (report.allocatedNodes ?? []).find(
    (candidate) => candidate.id === item.nodeId,
  );
  if (node) return `${node.name} · Node ${node.nodeIndex} of ${node.totalNodes}`;
  if (item.allocationId) return `Allocation ${item.allocationId.slice(-6)}`;
  return `Node ${item.nodeId.slice(-6)}`;
}

function ArtifactRow({
  item,
  report,
}: {
  item: RunArtifactItem;
  report: RunReportDetail;
}) {
  return (
    <div className="grid gap-3 border-t border-white/10 py-3 text-sm md:grid-cols-[1.1fr_0.8fr_0.6fr_0.7fr_0.5fr] md:items-center">
      <div>
        <p className="font-semibold text-white">{item.displayFilename}</p>
        <p className="text-xs text-text-muted">
          {artifactOwnerLabel(item, report)}
        </p>
        <p className="font-mono text-[11px] text-secondary">
          {item.relativePath}
        </p>
      </div>
      <div className="text-text-muted">
        {artifactLabel(item.artifactType)}
        {item.artifactType === "artifacts_zip" ? (
          <span className="ml-2 text-warning">Download-only archive</span>
        ) : null}
      </div>
      <div className="font-mono text-xs text-text-muted">
        {formatNumber(item.sizeBytes)} B
      </div>
      <div className="text-text-muted">{formatDate(item.createdAt)}</div>
      <a className="text-primary" href={item.downloadUrl}>
        Download
      </a>
    </div>
  );
}

function ArtifactsSection({
  report,
  runId,
  workspaceId,
}: {
  report: RunReportDetail;
  runId: string;
  workspaceId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const query = useQuery({
    enabled: expanded && report.artifactsSummary.count > 0,
    queryKey: ["run-artifacts", workspaceId, runId],
    queryFn: () => listRunArtifacts({ runId, workspaceId }),
  });
  return (
    <SectionCard title="Artifacts" testId="artifacts-section">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="primary">
            {report.artifactsSummary.count} artifacts
          </StatusPill>
          {report.artifactsSummary.hasArtifactsZip ? (
            <StatusPill tone="warning">Archive available</StatusPill>
          ) : null}
          {report.artifactsSummary.hasFinalStatsCsv ? (
            <StatusPill tone="success">Final stats ready</StatusPill>
          ) : null}
        </div>
        {report.artifactsSummary.count > 0 ? (
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            {expanded ? "Hide artifacts" : "Show artifacts"}
          </button>
        ) : null}
      </div>
      {report.artifactsSummary.count === 0 ? (
        <p className="mt-4 text-sm text-text-muted">
          No artifacts have been uploaded for this run yet.
        </p>
      ) : null}
      {expanded ? (
        <div className="mt-4">
          {query.isLoading ? (
            <p className="text-sm text-text-muted">Loading artifacts…</p>
          ) : null}
          {query.isError ? (
            <p className="text-sm text-error">Artifacts could not be loaded.</p>
          ) : null}
          {query.data?.items.map((item) => (
            <ArtifactRow item={item} key={item.id} report={report} />
          ))}
        </div>
      ) : null}
    </SectionCard>
  );
}

function NodesSection({ report }: { report: RunReportDetail }) {
  const nodes = report.allocatedNodes ?? [];
  return (
    <SectionCard title="Nodes">
      <div className="grid gap-3 md:grid-cols-2">
        {nodes.map((node) => {
          const terminal = runFailureDetail(node.terminalReason);
          return (
            <div
              className="rounded-2xl border border-white/10 bg-black/20 p-4"
              key={node.id}
            >
              <p className="font-semibold text-white">{node.name}</p>
              <p className="mt-1 text-sm text-text-muted">
                Node {node.nodeIndex} of {node.totalNodes} ·{" "}
                {formatEnum(node.scope)} · {formatEnum(node.state)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {node.slaResult ? (
                  <StatusPill tone={verdictTone(node.slaResult)}>
                    {slaLabel(node.slaResult)}
                  </StatusPill>
                ) : null}
                {node.cleanupStatus ? (
                  <StatusPill>{formatEnum(node.cleanupStatus)}</StatusPill>
                ) : null}
                {terminal ? (
                  <StatusPill tone="warning">{terminal.label}</StatusPill>
                ) : null}
              </div>
              <p className="mt-2 text-xs text-text-muted">
                Last heartbeat: {formatDate(node.lastHeartbeatAt)}
              </p>
              <p className="mt-2 font-mono text-[11px] text-secondary">
                {node.id}
              </p>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

export function RunReportPage() {
  const { runId = "" } = useParams();
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const queryClient = useQueryClient();
  const getWriteToken = useWriteToken();
  const [summaryPolls, setSummaryPolls] = useState(0);
  const queryKey = ["run-report", workspaceId, runId];
  const reportQuery = useQuery({
    enabled: Boolean(workspaceId && runId),
    queryKey,
    queryFn: () => loadRunReport(runId, workspaceId),
    retry: false,
    refetchInterval: (query) =>
      runReportRefetchInterval(
        query.state.data as RunReportDetail | undefined,
        summaryPolls,
      ),
    refetchIntervalInBackground: false,
  });
  const monitoringQuery = useQuery({
    enabled: Boolean(workspaceId && runId && reportQuery.data),
    queryKey: ["run-monitoring-link", workspaceId, runId],
    queryFn: () => getRunMonitoringLink(runId, workspaceId),
  });
  useEffect(() => {
    const report = reportQuery.data;
    if (
      report &&
      !activeRunStates.has(report.verdict.state) &&
      report.kpiSummary.status === "pending"
    ) {
      setSummaryPolls((value) => Math.min(value + 1, 12));
    } else if (report) {
      setSummaryPolls(0);
    }
  }, [reportQuery.data, reportQuery.dataUpdatedAt]);
  const validityMutation = useMutation({
    mutationFn: async (validity: RunValidity) =>
      patchRunValidity(runId, validity, workspaceId, await getWriteToken()),
    onSuccess: (response) => {
      queryClient.setQueryData<RunReportDetail>(queryKey, (current) =>
        current
          ? {
              ...current,
              verdict: { ...current.verdict, validity: response.validity },
            }
          : current,
      );
    },
  });
  const stopMutation = useMutation({
    mutationFn: async () => stopRun(runId, workspaceId, await getWriteToken()),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey }),
  });
  if (reportQuery.isLoading)
    return (
      <section className="mx-auto max-w-7xl text-text-muted">
        Loading report…
      </section>
    );
  if (reportQuery.isError || !reportQuery.data)
    return (
      <section className="mx-auto max-w-7xl text-error">
        Run Report could not be loaded.
      </section>
    );
  const report = reportQuery.data;
  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">
            Run Report
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-text-muted">
            Immutable snapshot, verdicts, final stats summary, and downloadable
            artifacts for this run.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <select
            aria-label="Report Validity"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-sm text-white"
            disabled={validityMutation.isPending}
            value={report.verdict.validity}
            onChange={(event) =>
              validityMutation.mutate(event.target.value as RunValidity)
            }
          >
            <option value="valid">Mark Valid</option>
            <option value="invalid">Mark Invalid</option>
          </select>
          {activeRunStates.has(report.verdict.state) ? (
            <button
              className="rounded-xl border border-warning/30 px-4 py-2 text-sm font-semibold text-warning"
              onClick={() => stopMutation.mutate()}
              type="button"
            >
              Stop Run
            </button>
          ) : null}
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
            onClick={() => reportQuery.refetch()}
            type="button"
          >
            Refresh
          </button>
          <Link
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
            to="/runs"
          >
            Back to Runs
          </Link>
        </div>
      </div>
      <VerdictSummary report={report} />
      <KpiSummary report={report} />
      <FailureDiagnostics report={report} />
      <MonitoringSection
        isLoading={monitoringQuery.isLoading}
        link={monitoringQuery.data}
      />
      <HttpTraceSection report={report} workspaceId={workspaceId} />
      <FinalStatsPreview report={report} />
      <SnapshotSummary report={report} />
      <ArtifactsSection
        report={report}
        runId={runId}
        workspaceId={workspaceId}
      />
      <NodesSection report={report} />
    </section>
  );
}
