import { useEffect, useState } from "react";
import { z } from "zod";
import { getCsrfToken, getRunReport, listRunArtifacts, patchRunValidity, stopRun, downloadRunArtifact, type RunArtifactItem, type RunReportDetail, type RunValidity } from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { activeRunStates, formatDate, formatDuration, formatEnum, formatMs, formatNumber, formatPercent, SectionCard, StatusPill } from "./run-shared";

const nullableStringSchema = z.string().nullable().optional();
const nullableNumberSchema = z.number().nullable().optional();
const dateTimeSchema = z.iso.datetime({ offset: true });
const nullableDateTimeSchema = dateTimeSchema.nullable().optional();
const reportRowSchema = z.object({
  label: nullableStringSchema,
  successRequests: nullableNumberSchema,
  totalRequests: nullableNumberSchema,
  failedRequests: nullableNumberSchema,
  errorRate: nullableNumberSchema,
  averageResponseTimeMs: nullableNumberSchema,
  p90Ms: nullableNumberSchema,
  p95Ms: nullableNumberSchema,
  p99Ms: nullableNumberSchema,
  responseCodeCounts: z.record(z.string(), z.number()).optional(),
}).passthrough();
const runReportEnvelopeSchema = z.object({
  id: z.string(),
  verdict: z.object({
    state: z.string(), runType: z.string(), sourceType: z.string(),
    validity: z.string(), slaResult: z.string(), slaResultReason: nullableStringSchema,
    durationMs: nullableNumberSchema, triggeredBy: z.object({ email: z.string() }).passthrough(),
    createdAt: dateTimeSchema, startedAt: nullableDateTimeSchema, endedAt: nullableDateTimeSchema,
    lastHeartbeatAt: nullableDateTimeSchema, failureReason: nullableStringSchema,
    forcedConvergence: z.boolean(),
  }).passthrough(),
  kpiSummary: z.object({
    status: z.string(), missingReasons: z.array(z.string()).optional(), totalRequests: nullableNumberSchema,
    failedRequests: nullableNumberSchema, errorRate: nullableNumberSchema,
    averageResponseTimeMs: nullableNumberSchema, p90Ms: nullableNumberSchema,
    p95Ms: nullableNumberSchema, p99Ms: nullableNumberSchema,
  }).passthrough(),
  failureDiagnostics: z.object({
    failureMessage: nullableStringSchema, failureReason: nullableStringSchema,
    hasFailedRequestsPreview: z.boolean(), notes: z.array(z.string()).optional(),
  }).passthrough(),
  finalStatsPreview: z.object({
    status: z.string(), rows: z.array(reportRowSchema), truncated: z.boolean(),
    warnings: z.array(z.string()).optional(),
  }).passthrough(),
  snapshot: z.object({
    scenarioCount: z.number(), slaRuleCount: z.number(), dependencyFileCount: z.number(),
    sourceName: nullableStringSchema, sourceRevision: nullableNumberSchema, envGroupName: nullableStringSchema,
    runMode: nullableStringSchema, scenarioItems: z.array(z.object({ scenarioName: z.string() }).passthrough()).optional(),
    scenarioNames: z.array(z.string()).optional(),
    slaRules: z.array(z.object({ metric: nullableStringSchema, condition: nullableStringSchema, thresholdText: nullableStringSchema }).passthrough()).optional(),
    dependencyFileNames: z.array(z.string()).optional(), envGroupVariableKeys: z.array(z.string()).optional(),
    resourceRequest: z.union([z.null(), z.object({ mode: nullableStringSchema, poolType: nullableStringSchema, selectedNodeId: nullableStringSchema, expectedConcurrencyPerNode: nullableNumberSchema }).passthrough()]).optional(),
  }).passthrough(),
  artifactsSummary: z.object({ count: z.number(), hasArtifactsZip: z.boolean(), hasFinalStatsCsv: z.boolean(), latestAvailableAt: nullableDateTimeSchema }).passthrough(),
}).passthrough();

async function loadRunReport(runId: string, workspaceId: string) {
  const report = await getRunReport(runId, workspaceId);
  const parsed = runReportEnvelopeSchema.safeParse(report);
  if (!parsed.success) throw new Error("Invalid Run Report response.");
  return parsed.data as RunReportDetail;
}

type Report = RunReportDetail;

export function runReportRefetchInterval(report: RunReportDetail | undefined, summaryPolls: number) {
  if (!report) return false;
  if (activeRunStates.has(report.verdict.state)) return 5000;
  if (report.kpiSummary.status === "pending" && summaryPolls < 12) return 5000;
  return false;
}
function reportTone(value: string) { return value === "finished" || value === "passed" || value === "valid" ? "success" : value === "failed" || value === "invalid" ? "error" : value === "aborted" || value === "not_evaluated" ? "warning" : "primary" as const; }
function slaLabel(value: string) { return value === "passed" ? "SLA passed" : value === "failed" ? "SLA failed" : "SLA not evaluated"; }
function Kpi({ label, value }: { label: string; value: string }) { return <div><small>{label}</small><strong style={{ display: "block", fontSize: 22, color: "#fff", marginTop: 6 }}>{value}</strong></div>; }

function Verdict({ report }: { report: Report }) { const v = report.verdict; return <SectionCard title="Verdict Summary"><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}><StatusPill tone={reportTone(v.state)}>{formatEnum(v.state)}</StatusPill><StatusPill tone="primary">{formatEnum(v.runType)}</StatusPill><StatusPill tone={reportTone(v.slaResult)}>{slaLabel(v.slaResult)}</StatusPill><StatusPill tone={reportTone(v.validity)}>{formatEnum(v.validity)}</StatusPill></div><dl><dt>Status</dt><dd>{formatEnum(v.state)}</dd><dt>Duration</dt><dd>{formatDuration(v.durationMs)}</dd><dt>Triggered by</dt><dd>{v.triggeredBy.email}</dd><dt>Created</dt><dd>{formatDate(v.createdAt)}</dd><dt>Started</dt><dd>{formatDate(v.startedAt)}</dd><dt>Ended</dt><dd>{formatDate(v.endedAt)}</dd><dt>Last heartbeat</dt><dd>{formatDate(v.lastHeartbeatAt)}</dd><dt>Forced convergence</dt><dd>{v.forcedConvergence ? "Yes" : "No"}</dd></dl>{activeRunStates.has(v.state) && <p>Run is still active. This report refreshes every 5 seconds.</p>}{v.failureReason && <p role="alert">Failure reason: {formatEnum(v.failureReason)}</p>}</SectionCard>; }
function KpiSummary({ report }: { report: Report }) { const k = report.kpiSummary; return <SectionCard title="KPI Summary">{k.status !== "parsed" && <p>{k.status === "missing" ? "Final stats artifact has not been uploaded yet." : "Summary not yet ready."}</p>}<div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))" }}><Kpi label="Total Requests" value={formatNumber(k.totalRequests)} /><Kpi label="Failed Requests" value={formatNumber(k.failedRequests)} /><Kpi label="Error Rate" value={formatPercent(k.errorRate)} /><Kpi label="Average Response Time" value={formatMs(k.averageResponseTimeMs)} /><Kpi label="P90" value={formatMs(k.p90Ms)} /><Kpi label="P95" value={formatMs(k.p95Ms)} /><Kpi label="P99" value={formatMs(k.p99Ms)} /></div>{k.missingReasons?.length && <p>Missing: {k.missingReasons.map(formatEnum).join(", ")}</p>}</SectionCard>; }
function FailureDiagnostics({ report }: { report: Report }) { const d = report.failureDiagnostics; if (!d.failureReason && !d.failureMessage && !d.notes?.length) return null; return <SectionCard title="Failure Diagnostics"><p>{d.failureReason ? `Reason: ${formatEnum(d.failureReason)}` : "The run reported a failure."}</p>{d.failureMessage && <p role="alert">{d.failureMessage}</p>}{d.notes?.map((note) => <StatusPill key={note} tone="warning">{formatEnum(note)}</StatusPill>)}<p>Download logs or the archive from Artifacts for deeper troubleshooting.</p></SectionCard>; }
function FinalStats({ report }: { report: Report }) { const p = report.finalStatsPreview; return <SectionCard title="Final Stats Preview">{p.status !== "parsed" && <p>{p.status === "missing" ? "No final stats rows are available yet." : p.status === "failed" ? "Final stats summary is unavailable. Raw artifacts can still be downloaded." : "Summary is pending."}</p>}{p.warnings?.map((w) => <StatusPill key={w} tone="warning">{formatEnum(w)}</StatusPill>)}{p.status === "parsed" && <div style={{ overflowX: "auto" }}><table><thead><tr><th>Label</th><th>Total</th><th>Failed</th><th>Error Rate</th><th>Avg RT</th><th>P95</th><th>Codes</th></tr></thead><tbody>{p.rows.map((r, i) => <tr key={`${r.label}-${i}`}><td>{r.label ?? "Total"}</td><td>{formatNumber(r.totalRequests)}</td><td>{formatNumber(r.failedRequests)}</td><td>{formatPercent(r.errorRate)}</td><td>{formatMs(r.averageResponseTimeMs)}</td><td>{formatMs(r.p95Ms)}</td><td>{Object.entries(r.responseCodeCounts ?? {}).map(([code, n]) => `${code}: ${n}`).join(", ") || "N/A"}</td></tr>)}</tbody></table></div>}</SectionCard>; }
function Snapshot({ report }: { report: Report }) { const s = report.snapshot; return <SectionCard title="Snapshot Summary"><dl><dt>Source</dt><dd>{s.sourceName ?? "N/A"}</dd><dt>Revision</dt><dd>{s.sourceRevision ?? "N/A"}</dd><dt>Environment</dt><dd>{s.envGroupName ?? "N/A"}</dd><dt>Run mode</dt><dd>{formatEnum(s.runMode)}</dd><dt>Scenarios</dt><dd>{s.scenarioCount}</dd><dt>SLA rules</dt><dd>{s.slaRuleCount}</dd><dt>Dependency files</dt><dd>{s.dependencyFileCount}</dd><dt>Node mode</dt><dd>{formatEnum(s.resourceRequest?.mode)}</dd><dt>Expected concurrency</dt><dd>{s.resourceRequest?.expectedConcurrencyPerNode ?? "N/A"}</dd></dl>{s.scenarioNames?.length && <p>Scenarios: {s.scenarioNames.join(", ")}</p>}{s.slaRules?.length && <p>SLA rules: {s.slaRules.map((r) => [r.metric, r.condition, r.thresholdText].filter(Boolean).join(" ")).join(" · ")}</p>}{s.dependencyFileNames?.length && <p>Dependency files: {s.dependencyFileNames.join(", ")}</p>}</SectionCard>; }
function Artifacts({ report, runId, workspaceId }: { report: Report; runId: string; workspaceId: string }) { const [open, setOpen] = useState(false); const [items, setItems] = useState<RunArtifactItem[]>([]); const [error, setError] = useState<string | null>(null); useEffect(() => { if (!open || !report.artifactsSummary.count) return; void listRunArtifacts({ runId, workspaceId }).then((r) => setItems(r.items)).catch(() => setError("Artifacts could not be loaded.")); }, [open, report.artifactsSummary.count, runId, workspaceId]); async function download(item: RunArtifactItem) { try { const blob = await downloadRunArtifact(runId, item.id, workspaceId); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = item.displayFilename; link.click(); URL.revokeObjectURL(link.href); } catch { setError("Artifact download failed."); } } return <SectionCard title="Artifacts"><p>{report.artifactsSummary.count} artifacts · {report.artifactsSummary.hasFinalStatsCsv ? "Final stats ready" : "Final stats pending"}{report.artifactsSummary.hasArtifactsZip ? " · Archive available" : ""}</p>{report.artifactsSummary.count > 0 && <button type="button" onClick={() => setOpen(!open)}>{open ? "Hide artifacts" : "Show artifacts"}</button>}{report.artifactsSummary.count === 0 && <p>No artifacts have been uploaded for this run yet.</p>}{error && <p role="alert">{error}</p>}{open && <div>{items.map((item) => <p key={item.id}><strong>{item.displayFilename}</strong> · {formatEnum(item.artifactType)} · {formatNumber(item.sizeBytes)} B <button type="button" onClick={() => void download(item)}>Download</button></p>)}</div>}</SectionCard>; }
function Nodes({ report }: { report: RunReportDetail }) {
  const request = report.snapshot.resourceRequest;
  return <SectionCard title="Nodes"><div><strong>Selected Load Node</strong><dl><dt>Node ID</dt><dd>{request?.selectedNodeId ?? "N/A"}</dd><dt>Mode</dt><dd>{formatEnum(request?.mode)}</dd><dt>Pool</dt><dd>{formatEnum(request?.poolType)}</dd><dt>Expected concurrency</dt><dd>{request?.expectedConcurrencyPerNode ?? "N/A"}</dd></dl></div></SectionCard>;
}

export function RunReportPage({ runId }: { runId: string }) { const { session, csrfToken } = useAuthSession(); const workspaceId = session?.defaultWorkspace.id ?? ""; const [report, setReport] = useState<RunReportDetail | null>(null); const [error, setError] = useState<string | null>(null); const [polls, setPolls] = useState(0); const [summaryPolls, setSummaryPolls] = useState(0); const [saving, setSaving] = useState(false); useEffect(() => { let cancelled = false; async function load() { try { const next = await loadRunReport(runId, workspaceId); if (!cancelled) { setReport(next); setError(null); } } catch { if (!cancelled) setError("Run Report could not be loaded."); } } if (workspaceId && runId) void load(); return () => { cancelled = true; }; }, [runId, workspaceId, polls]); useEffect(() => { if (!report) return; if (!activeRunStates.has(report.verdict.state) && report.kpiSummary.status === "pending") setSummaryPolls((n) => Math.min(n + 1, 12)); else setSummaryPolls(0); }, [report]); useEffect(() => { if (!report || runReportRefetchInterval(report, summaryPolls) === false) return; const timer = window.setTimeout(() => setPolls((n) => n + 1), 5000); return () => window.clearTimeout(timer); }, [report, summaryPolls]); if (error && !report) return <main><p role="alert">{error}</p></main>; if (!report) return <main><p>Loading report…</p></main>; async function validity(value: RunValidity) { setSaving(true); try { const response = await patchRunValidity(runId, value, workspaceId, csrfToken ?? (await getCsrfToken()).csrfToken); setReport({ ...report, verdict: { ...report.verdict, validity: response.validity } }); } catch { setError("Unable to update validity."); } finally { setSaving(false); } } async function stop() { try { await stopRun(runId, workspaceId, csrfToken ?? (await getCsrfToken()).csrfToken); setPolls((n) => n + 1); } catch { setError("Unable to stop this run."); } } return <main><p><a href="/runs">Runs</a> / {runId}</p><h1>Run Report</h1><p>Immutable snapshot, verdicts, final stats summary, and downloadable artifacts for this run.</p><div><label>Validity <select disabled={saving} value={report.verdict.validity} onChange={(e) => void validity(e.target.value as RunValidity)}><option value="valid">Mark Valid</option><option value="invalid">Mark Invalid</option></select></label>{activeRunStates.has(report.verdict.state) && <button type="button" onClick={() => void stop()}>Stop Run</button>}<button type="button" onClick={() => setPolls((n) => n + 1)}>Refresh</button></div>{error && <p role="alert">{error}</p>}<Verdict report={report}/><KpiSummary report={report}/><FailureDiagnostics report={report}/><FinalStats report={report}/><Snapshot report={report}/><Artifacts report={report} runId={runId} workspaceId={workspaceId}/><Nodes report={report}/></main>; }
