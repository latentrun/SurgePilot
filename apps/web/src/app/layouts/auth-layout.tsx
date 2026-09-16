import { Link } from "react-router-dom";

import { SurgePilotLogo } from "../../components/surgepilot-logo";

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
    <main className="surgepilot-aurora-surface relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 text-text-main antialiased">
      <section className="relative z-10 flex w-full max-w-[440px] flex-col items-center">
        <div className="mb-6 flex w-full flex-col items-start">
          <Link
            className="mb-6 flex items-center gap-3 text-primary"
            to="/login"
          >
            <span className="grid h-10 w-10 place-items-center rounded-lg border border-primary/30 bg-primary/10 text-primary shadow-[0_0_22px_rgba(34,211,238,0.18)]">
              <SurgePilotLogo className="h-7 w-7" />
            </span>
            <span className="font-display text-[26px] font-semibold leading-8 text-text-main">
              SurgePilot
            </span>
          </Link>
          <p className="mb-3 font-mono text-[10px] font-semibold uppercase leading-3 text-secondary">
            Secure access
          </p>
          <h1 className="font-display text-[28px] font-semibold leading-9 text-white">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            {description}
          </p>
        </div>

        <div className="surgepilot-glass w-full overflow-hidden rounded-2xl">
          <div className="h-px w-full surgepilot-hairline" />
          <div className="p-6 md:p-8">{children}</div>
        </div>

        <p className="mt-6 flex items-center justify-center gap-2 text-center font-mono text-[11px] leading-4 text-secondary">
          <SurgePilotLogo decorative className="h-3.5 w-3.5 text-primary" />
          {footerText}
        </p>
      </section>
    </main>
  );
}
