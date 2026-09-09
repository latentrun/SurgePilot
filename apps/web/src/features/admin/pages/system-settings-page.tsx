import { useEffect, useState } from "react";

import { ApiError, getCsrfToken, getSystemSettings, patchSystemSettings, type SystemSettingsPatchRequest } from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

export function AdminSystemSettingsPage() {
  const { csrfToken, session } = useAuthSession();
  const [form, setForm] = useState<SystemSettingsPatchRequest>({});
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const isAdmin = session?.permissions.canManageSystemSettings === true;
  useEffect(() => {
    if (!isAdmin) return;
    void getSystemSettings().then((result) => { setForm(result.settings); }).catch((cause) => { setStatus(cause instanceof ApiError ? cause.message : "Settings could not be loaded."); }).finally(() => setLoading(false));
  }, [isAdmin]);
  if (!isAdmin) return <AdminForbidden />;
  function update<K extends keyof SystemSettingsPatchRequest>(key: K, value: SystemSettingsPatchRequest[K]) { setForm((current) => ({ ...current, [key]: value })); }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    try { await patchSystemSettings(form, csrfToken ?? (await getCsrfToken()).csrfToken); setStatus("Settings saved."); }
    catch (cause) { setStatus(cause instanceof ApiError ? cause.message : "Settings could not be saved."); }
  }
  return <section>
    <h1>System Settings</h1>
    <p>Manage DB-backed runtime policies. Secrets and deployment settings remain outside the web console.</p>
    {loading ? <p>Loading settings…</p> : <form onSubmit={(event) => void save(event)}>
      <label><input checked={form.allowSignup ?? false} onChange={(event) => update("allowSignup", event.target.checked)} type="checkbox" /> Allow local signup</label>
      <label>Soft concurrency warning <input min="1" onChange={(event) => update("loadSoftLimitWarningConcurrency", Number(event.target.value))} type="number" value={form.loadSoftLimitWarningConcurrency ?? ""} /></label>
      <label>JMeter memory <input onChange={(event) => update("jmeterMemoryXmx", event.target.value)} value={form.jmeterMemoryXmx ?? ""} /></label>
      <label>Max run duration (seconds) <input min="1" onChange={(event) => update("maxRunDurationSeconds", Number(event.target.value))} type="number" value={form.maxRunDurationSeconds ?? ""} /></label>
      <label>Max target RPS <input min="1" onChange={(event) => update("maxTargetRps", Number(event.target.value))} type="number" value={form.maxTargetRps ?? ""} /></label>
      <button type="submit">Save Settings</button>
    </form>}
    {status ? <p role="status">{status}</p> : null}
  </section>;
}
