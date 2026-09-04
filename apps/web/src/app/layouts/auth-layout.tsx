type AuthLayoutProps = Readonly<{
  children: React.ReactNode;
  description: string;
  footerText: string;
  title: string;
}>;

export function AuthLayout({
  children,
  description,
  footerText,
  title,
}: AuthLayoutProps) {
  return (
    <main>
      <section aria-labelledby="auth-title">
        <a href="/login" aria-label="SurgePilot home">
          <span>SurgePilot</span>
        </a>
        <p>Secure access</p>
        <h1 id="auth-title">{title}</h1>
        <p>{description}</p>
        <div>{children}</div>
        <p>{footerText}</p>
      </section>
    </main>
  );
}
