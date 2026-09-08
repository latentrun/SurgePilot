export function AdminForbidden() {
  return (
    <main>
      <section role="alert">
        <p>403</p>
        <h1>Admin access required</h1>
        <p>
          You do not have permission to manage SurgePilot administration
          settings.
        </p>
      </section>
    </main>
  );
}
