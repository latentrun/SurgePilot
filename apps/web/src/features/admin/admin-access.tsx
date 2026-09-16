export function AdminForbidden() {
  return (
    <section className="mx-auto max-w-3xl rounded-3xl border border-error/30 bg-error-container p-6 text-on-error-container">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em]">
        403
      </p>
      <h1 className="mt-3 font-display text-2xl font-semibold">
        Admin access required
      </h1>
      <p className="mt-2 text-sm leading-6">
        You do not have permission to manage SurgePilot administration settings.
      </p>
    </section>
  );
}
