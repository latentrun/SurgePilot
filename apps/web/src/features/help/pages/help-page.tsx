import { useState } from "react";

import { ApiError, downloadPublicApiAiSkill } from "../../../app/api-client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../../components/ui/tabs";
import { HELP_COPY, HELP_TABS } from "../copy";

const archiveFilename = "surgepilot-public-api-skill.zip";

function Icon({ children }: { children: string }) {
  return <span aria-hidden className="text-primary" role="img">{children}</span>;
}

function downloadErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "UNAUTHENTICATED") return HELP_COPY.errors.sessionExpired;
    if (error.body.code === "AI_SKILL_SOURCE_NOT_AVAILABLE") return HELP_COPY.errors.sourceUnavailable;
  }
  return HELP_COPY.errors.generic;
}

function GuidanceList({ items }: { items: readonly string[] }) {
  return <ul className="mt-6 grid gap-3">{items.map((item) => <li className="flex gap-3 rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-text-muted" key={item}><span aria-hidden className="mt-1 flex-none text-success">✓</span><span>{item}</span></li>)}</ul>;
}

function TopicHeader({ description, icon, title }: { description: string; icon: string; title: string }) {
  return <div className="flex flex-col gap-5 border-b border-white/10 pb-7 sm:flex-row sm:items-start sm:justify-between"><div className="max-w-2xl"><p className="font-mono text-[10px] font-semibold uppercase tracking-[0.24em] text-primary">{HELP_COPY.topicEyebrow}</p><h2 className="mt-3 font-display text-2xl font-semibold text-white sm:text-3xl">{title}</h2><p className="mt-3 text-sm leading-7 text-text-muted">{description}</p></div><div className="grid h-12 w-12 flex-none place-items-center rounded-2xl border border-primary/20 bg-primary/10 text-xl">{icon}</div></div>;
}

export function HelpPage() {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);

  async function handleDownload() {
    setIsDownloading(true); setDownloadError(null); setDownloadStatus(null);
    try {
      const blob = await downloadPublicApiAiSkill();
      const objectUrl = URL.createObjectURL(blob);
      try {
        const anchor = document.createElement("a");
        anchor.href = objectUrl; anchor.download = archiveFilename; document.body.append(anchor); anchor.click(); anchor.remove();
      } finally { URL.revokeObjectURL(objectUrl); }
      setDownloadStatus(HELP_COPY.aiAgents.downloadSuccess);
    } catch (error) { setDownloadError(downloadErrorMessage(error)); }
    finally { setIsDownloading(false); }
  }

  return <section className="mx-auto w-full max-w-container-max pb-8">
    <header className="relative overflow-hidden rounded-3xl border border-white/10 bg-surface-container-low px-6 py-7 shadow-2xl shadow-black/20 sm:px-8 sm:py-9"><div className="relative grid gap-7 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end"><div><div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-primary"><Icon>✦</Icon>{HELP_COPY.eyebrow}</div><h1 className="mt-5 font-display text-4xl font-semibold tracking-[-0.03em] text-white sm:text-5xl">{HELP_COPY.title}</h1><p className="mt-4 max-w-3xl text-sm leading-7 text-text-muted sm:text-base">{HELP_COPY.introduction}</p></div><div className="grid grid-cols-3 gap-2 rounded-2xl border border-white/10 bg-black/20 p-3">{HELP_COPY.headerFacts.map((fact) => <div className="min-w-0 rounded-xl bg-white/[0.04] px-3 py-3" key={fact.label}><p className="font-mono text-[9px] uppercase tracking-[0.18em] text-secondary">{fact.label}</p><p className="mt-1 truncate text-xs font-semibold text-white">{fact.value}</p></div>)}</div></div></header>
    <Tabs className="mt-6" defaultValue="getting-started"><div className="overflow-x-auto rounded-t-2xl border border-b-0 border-white/10 bg-surface-container-low px-2"><TabsList aria-label={HELP_COPY.topicsLabel}>{HELP_TABS.map((tab) => <TabsTrigger key={tab.value} value={tab.value}>{tab.label}</TabsTrigger>)}</TabsList></div><div className="rounded-b-3xl border border-white/10 bg-surface-container-low p-6 shadow-xl sm:p-8">
      <TabsContent value="getting-started"><TopicHeader description={HELP_COPY.gettingStarted.description} icon="◉" title={HELP_COPY.gettingStarted.title} /><div className="mt-7 grid gap-4 lg:grid-cols-3">{HELP_COPY.gettingStarted.steps.map((step) => <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5" key={step.number}><span className="font-mono text-xs font-semibold text-primary">{step.number}</span><h3 className="mt-7 text-base font-semibold text-white">{step.title}</h3><p className="mt-3 text-sm leading-6 text-text-muted">{step.body}</p></article>)}</div></TabsContent>
      <TabsContent value="ai-agents"><TopicHeader description={HELP_COPY.aiAgents.description} icon="◈" title={HELP_COPY.aiAgents.title} /><div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]"><div><div className="grid gap-3 sm:grid-cols-3">{HELP_COPY.aiAgents.cards.map((card) => <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4" key={card.title}><Icon>◆</Icon><p className="mt-4 text-sm font-semibold text-white">{card.title}</p><p className="mt-1 text-xs text-text-muted">{card.body}</p></div>)}</div><GuidanceList items={HELP_COPY.aiAgents.checklist} /></div><aside className="h-fit rounded-3xl border border-primary/20 bg-primary/10 p-6"><div className="flex items-center justify-between gap-4"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary text-on-primary">▣</div><span className="rounded-full border border-white/10 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.18em] text-secondary">{HELP_COPY.aiAgents.archiveLabel}</span></div><h3 className="mt-6 text-lg font-semibold text-white">{HELP_COPY.aiAgents.downloadTitle}</h3><p className="mt-3 text-sm leading-6 text-text-muted">{HELP_COPY.aiAgents.downloadDescription}</p><button className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-on-primary disabled:cursor-wait disabled:opacity-60" disabled={isDownloading} onClick={() => void handleDownload()} type="button">⇩ {isDownloading ? HELP_COPY.aiAgents.downloadPending : HELP_COPY.aiAgents.downloadButton}</button>{downloadStatus ? <p className="mt-3 text-xs font-medium text-success" role="status">{downloadStatus}</p> : null}{downloadError ? <p className="mt-3 text-xs leading-5 text-error" role="alert">{downloadError}</p> : null}</aside></div></TabsContent>
      <TabsContent value="scripting"><TopicHeader description={HELP_COPY.scripting.description} icon="▤" title={HELP_COPY.scripting.title} /><GuidanceList items={HELP_COPY.scripting.points} /></TabsContent>
      <TabsContent value="api-catalog"><TopicHeader description={HELP_COPY.apiCatalog.description} icon="▦" title={HELP_COPY.apiCatalog.title} /><GuidanceList items={HELP_COPY.apiCatalog.points} /></TabsContent>
      <TabsContent value="troubleshooting"><TopicHeader description={HELP_COPY.troubleshooting.description} icon="⌁" title={HELP_COPY.troubleshooting.title} /><GuidanceList items={HELP_COPY.troubleshooting.points} /></TabsContent>
      <TabsContent value="limits-activation"><TopicHeader description={HELP_COPY.limits.description} icon="▣" title={HELP_COPY.limits.title} /><div className="mt-7 grid gap-4 lg:grid-cols-2"><article className="rounded-2xl border border-success/25 bg-success/10 p-5"><span className="text-success">✓</span><h3 className="mt-5 text-lg font-semibold text-white">{HELP_COPY.limits.activeTitle}</h3><p className="mt-3 text-sm leading-7 text-text-muted">{HELP_COPY.limits.activeBody}</p></article><article className="rounded-2xl border border-warning/25 bg-warning/10 p-5"><span className="text-warning">!</span><h3 className="mt-5 text-lg font-semibold text-white">{HELP_COPY.limits.inactiveTitle}</h3><p className="mt-3 text-sm leading-7 text-text-muted">{HELP_COPY.limits.inactiveBody}</p></article></div><p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm leading-6 text-text-muted">{HELP_COPY.limits.boundary}</p></TabsContent>
    </div></Tabs>
  </section>;
}
