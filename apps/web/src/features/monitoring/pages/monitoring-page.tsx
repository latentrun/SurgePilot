import { useEffect, useMemo, useState } from "react";

import {
  getMonitoringEmbed,
  type MonitoringEmbedResponse,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { formatEnum, StatusPill } from "../../runs/pages/run-shared";

type MonitoringStatus = MonitoringEmbedResponse["status"];
type IframeFailureReason = "auth" | "gateway" | "grafana";

const monitoringStateCopy: Record<
  MonitoringStatus,
  { body: string; title: string }
> = {
  ready: {
    body: "Dashboard configuration is ready. Loading the dashboard…",
    title: "Monitoring is ready",
  },
  not_configured: {
    body: "This deployment has no monitoring configuration, so no dashboard is available.",
    title: "Monitoring is not configured",
  },
  config_error: {
    body: "Monitoring configuration is incomplete, so the dashboard cannot be shown.",
    title: "Monitoring configuration error",
  },
  disabled: {
    body: "Monitoring is disabled for this deployment.",
    title: "Monitoring is disabled",
  },
};

function failureReasonForStatus(status: number): IframeFailureReason {
  if (status === 401 || status === 403) return "auth";
  if (status === 502 || status === 503 || status === 504) return "gateway";
  return "grafana";
}

function monitoringFailureCopy(reason: IframeFailureReason | undefined) {
  if (reason === "gateway") {
    return "The monitoring dashboard is temporarily unavailable. Try again later.";
  }
  if (reason === "auth") {
    return "The monitoring dashboard could not be loaded. Check your session, then try again.";
  }
  return "The monitoring dashboard could not be loaded. Try again later.";
}

export function useMonitoringQueryParams() {
  const [search, setSearch] = useState(() => window.location.search);
  useEffect(() => {
    const onPopState = () => setSearch(window.location.search);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  return useMemo(() => new URLSearchParams(search), [search]);
}

type IframeState = {
  failureReason?: IframeFailureReason;
  status: "checking" | "loading" | "loaded" | "failed";
  url: string | null;
};

export function MonitoringPage() {
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const searchParams = useMonitoringQueryParams();
  const runId = searchParams.get("runId");
  const from = searchParams.get("from");
  const to = searchParams.get("to");

  const [response, setResponse] = useState<MonitoringEmbedResponse | null>(
    null,
  );
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [iframeState, setIframeState] = useState<IframeState>({
    status: "loading",
    url: null,
  });

  useEffect(() => {
    if (!workspaceId) return undefined;
    let cancelled = false;
    setIsLoading(true);
    void getMonitoringEmbed({ from, runId, to, workspaceId })
      .then((next) => {
        if (cancelled) return;
        setResponse(next);
        setLoadError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setResponse(null);
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, runId, from, to]);

  const iframeUrl = response?.iframeUrl ?? null;

  useEffect(() => {
    setIframeState((current) =>
      current.url === iframeUrl ? current : { status: "loading", url: iframeUrl },
    );
  }, [iframeUrl]);

  useEffect(() => {
    if (!iframeUrl) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    setIframeState({ status: "checking", url: iframeUrl });
    void (async () => {
      try {
        const preflight = await fetch(iframeUrl, {
          credentials: "include",
          signal: controller.signal,
        });
        if (cancelled) return;
        setIframeState({
          failureReason: preflight.ok
            ? undefined
            : failureReasonForStatus(preflight.status),
          status: preflight.ok ? "loading" : "failed",
          url: iframeUrl,
        });
      } catch (error: unknown) {
        if (cancelled) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setIframeState({
          failureReason: "gateway",
          status: "failed",
          url: iframeUrl,
        });
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [iframeUrl]);

  const stateCopy = response ? monitoringStateCopy[response.status] : null;
  const showStatePanel = Boolean(response) && response?.status !== "ready";
  const showIframe =
    Boolean(response?.enabled) &&
    iframeUrl !== null &&
    iframeState.status !== "checking" &&
    iframeState.status !== "failed";

  return (
    <main
      data-monitoring-page="true"
      style={{
        background: "#0b0f1a",
        display: "flex",
        flexDirection: "column",
        height: "100dvh",
        margin: 0,
        maxWidth: "none",
        minHeight: 0,
        width: "100%",
      }}
    >
      <header
        style={{
          alignItems: "center",
          display: "flex",
          gap: 12,
          padding: "12px 16px",
        }}
      >
        <h1 style={{ color: "#fff", fontSize: 18, margin: 0 }}>Monitoring</h1>
        {response ? (
          <StatusPill tone={response.enabled ? "success" : "warning"}>
            {formatEnum(response.status)}
          </StatusPill>
        ) : null}
      </header>

      <div
        aria-label="Monitoring"
        role="region"
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          minHeight: 0,
          position: "relative",
        }}
      >
        {isLoading ? (
          <p role="status" style={{ color: "#bbc9cd", margin: 16 }}>
            Loading monitoring dashboard…
          </p>
        ) : null}
        {loadError ? (
          <p role="alert" style={{ margin: 16 }}>
            Monitoring could not be loaded.
          </p>
        ) : null}
        {!isLoading && response?.status === "ready" && iframeState.status !== "loaded" ? (
          <p
            data-monitoring-state="ready"
            role="status"
            style={{ color: "#bbc9cd", margin: 16 }}
          >
            {monitoringStateCopy.ready.body}
          </p>
        ) : null}
        {!isLoading && showStatePanel ? (
          <div
            data-monitoring-state={response?.status}
            role="status"
            style={{
              border: "1px solid #d3bbff55",
              borderRadius: 16,
              margin: 16,
              maxWidth: 640,
              padding: 16,
            }}
          >
            <h2 style={{ color: "#fff", fontSize: 16, margin: 0 }}>
              {stateCopy?.title}
            </h2>
            <p style={{ color: "#bbc9cd", marginTop: 8 }}>{stateCopy?.body}</p>
            {response?.warnings?.length ? (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  marginTop: 12,
                }}
              >
                {response.warnings.map((warning) => (
                  <StatusPill key={warning} tone="warning">
                    {formatEnum(warning)}
                  </StatusPill>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {iframeState.status === "failed" ? (
          <p
            data-monitoring-state="iframe_failed"
            role="alert"
            style={{ margin: 16 }}
          >
            {monitoringFailureCopy(iframeState.failureReason)}
          </p>
        ) : null}
        {showIframe ? (
          <iframe
            onError={() =>
              setIframeState({
                failureReason: "grafana",
                status: "failed",
                url: iframeUrl,
              })
            }
            onLoad={() => setIframeState({ status: "loaded", url: iframeUrl })}
            src={iframeUrl ?? undefined}
            style={{ border: 0, flex: 1, minHeight: 0, width: "100%" }}
            title="Grafana monitoring dashboard"
          />
        ) : null}
      </div>
    </main>
  );
}
