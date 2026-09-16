import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import {
  getMonitoringEmbed,
  type MonitoringEmbedResponse,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { formatEnum, StatusPill } from "../../runs/pages/run-shared";

type IframeFailureReason = "auth" | "gateway" | "grafana";

function monitoringStatusCopy(response: MonitoringEmbedResponse | undefined) {
  if (!response) return "Loading monitoring dashboard…";
  if (response.status === "disabled") return "Monitoring is disabled.";
  if (
    response.status === "not_configured" ||
    response.status === "config_error"
  ) {
    return "Monitoring is not configured. Ask an administrator to enable the Grafana and InfluxDB services.";
  }
  return "Dashboard configuration is ready. Loading Grafana…";
}

function failureReasonForStatus(status: number): IframeFailureReason {
  if (status === 401 || status === 403) return "auth";
  if (status === 502 || status === 503 || status === 504) return "gateway";
  return "grafana";
}

function grafanaFailureCopy(reason: IframeFailureReason | undefined) {
  if (reason === "gateway") {
    return "Grafana gateway is unavailable. Restarting Grafana or Nginx may be required.";
  }
  if (reason === "auth") {
    return "Grafana dashboard could not be loaded. Check your session, then try again.";
  }
  return "Grafana dashboard could not be loaded. Check the Grafana provisioning status, then try again.";
}

export function MonitoringPage() {
  const [searchParams] = useSearchParams();
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const runId = searchParams.get("runId");
  const from = searchParams.get("from");
  const to = searchParams.get("to");
  const embedQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["monitoring-embed", workspaceId, runId, from, to],
    queryFn: () => getMonitoringEmbed({ workspaceId, runId, from, to }),
  });
  const response = embedQuery.data;
  const [iframeState, setIframeState] = useState<{
    status: "checking" | "loading" | "loaded" | "failed";
    url: string | null;
    failureReason?: IframeFailureReason;
  }>({ status: "loading", url: null });
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  useEffect(() => {
    setIframeState((current) =>
      current.url === (response?.iframeUrl ?? null)
        ? current
        : {
            status: response?.iframeUrl ? "checking" : "loading",
            url: response?.iframeUrl ?? null,
          },
    );
  }, [response?.iframeUrl]);

  useEffect(() => {
    const iframeUrl = response?.iframeUrl ?? null;
    if (!iframeUrl) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    setIframeState({ status: "checking", url: iframeUrl });
    void (async () => {
      try {
        const grafanaResponse = await fetch(iframeUrl, {
          credentials: "include",
          signal: controller.signal,
        });
        if (cancelled) return;
        setIframeState({
          status: grafanaResponse.ok ? "loading" : "failed",
          url: iframeUrl,
          failureReason: grafanaResponse.ok
            ? undefined
            : failureReasonForStatus(grafanaResponse.status),
        });
      } catch (error: unknown) {
        if (cancelled) return;
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        setIframeState({
          status: "failed",
          url: iframeUrl,
          failureReason: "gateway",
        });
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [response?.iframeUrl]);

  useEffect(() => {
    const iframe = iframeRef.current;
    const iframeUrl = response?.iframeUrl ?? null;
    if (!iframe || !iframeUrl) return undefined;
    const markLoaded = () =>
      setIframeState({ status: "loaded", url: iframeUrl });
    const markFailed = () =>
      setIframeState({
        status: "failed",
        url: iframeUrl,
        failureReason: "grafana",
      });
    iframe.addEventListener("load", markLoaded);
    iframe.addEventListener("error", markFailed);
    return () => {
      iframe.removeEventListener("load", markLoaded);
      iframe.removeEventListener("error", markFailed);
    };
  }, [response?.iframeUrl]);

  return (
    <section
      className="flex h-[calc(100dvh-4rem)] min-h-0 w-full flex-col bg-background"
      data-monitoring-page="true"
    >
      <h1 className="sr-only">Monitoring</h1>

      <div
        aria-label="Monitoring"
        className="relative flex min-h-0 flex-1 flex-col"
        role="region"
      >
        {response ? (
          <div className="absolute right-4 top-4 z-10">
            <StatusPill tone={response.enabled ? "success" : "warning"}>
              {formatEnum(response.status)}
            </StatusPill>
          </div>
        ) : null}
        {embedQuery.isLoading ? (
          <div
            className="absolute left-4 top-4 z-10 rounded-xl border border-white/10 bg-surface-container-low/90 px-3 py-2 text-sm text-text-muted shadow-lg"
            role="status"
          >
            Loading monitoring dashboard…
          </div>
        ) : null}
        {embedQuery.isError ? (
          <div
            className="absolute left-4 top-4 z-10 rounded-xl border border-error/30 bg-error-container px-3 py-2 text-sm text-on-error-container shadow-lg"
            role="status"
          >
            Monitoring could not be loaded.
          </div>
        ) : null}
        {response && !response.enabled ? (
          <div
            className="m-4 max-w-2xl rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
            role="status"
          >
            <p>{monitoringStatusCopy(response)}</p>
            {response.warnings?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {response.warnings.map((warning) => (
                  <StatusPill key={warning} tone="warning">
                    {formatEnum(warning)}
                  </StatusPill>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {response?.enabled && response.iframeUrl ? (
          <>
            {iframeState.status === "failed" ? (
              <div
                className="absolute left-4 top-4 z-10 rounded-xl border border-error/30 bg-error-container px-3 py-2 text-sm text-on-error-container shadow-lg"
                role="status"
              >
                {grafanaFailureCopy(iframeState.failureReason)}
              </div>
            ) : null}
            {iframeState.status !== "checking" &&
            iframeState.status !== "failed" ? (
              <iframe
                className="min-h-0 flex-1 w-full border-0 bg-surface-container-low"
                onError={() =>
                  setIframeState({
                    status: "failed",
                    url: response.iframeUrl ?? null,
                    failureReason: "grafana",
                  })
                }
                onLoad={() =>
                  setIframeState({
                    status: "loaded",
                    url: response.iframeUrl ?? null,
                  })
                }
                ref={iframeRef}
                src={response.iframeUrl}
                title="Grafana monitoring dashboard"
              />
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}
