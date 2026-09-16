export function LoadingPage() {
  return (
    <main className="surgepilot-aurora-surface grid min-h-screen place-items-center px-4 text-text-main">
      <div className="surgepilot-glass flex items-center gap-3 rounded-lg px-4 py-3 font-mono text-xs text-text-muted">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary-container shadow-[0_0_12px_rgba(34,211,238,0.6)]" />
        Loading
      </div>
    </main>
  );
}
