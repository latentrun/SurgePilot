type FieldProps = Readonly<{
  autoComplete?: string;
  error?: string;
  helpText?: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type: "email" | "password" | "text";
  value: string;
}>;

export function Field({
  autoComplete,
  error,
  helpText,
  label,
  name,
  onChange,
  placeholder,
  type,
  value,
}: FieldProps) {
  const hintId = `${name}-hint`;
  const errorId = `${name}-error`;
  const describedBy = [helpText ? hintId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="flex flex-col gap-2">
      <label
        className="font-mono text-[11px] font-semibold uppercase leading-4 text-secondary"
        htmlFor={name}
      >
        {label}
      </label>
      <input
        aria-describedby={describedBy || undefined}
        aria-invalid={error ? "true" : undefined}
        autoComplete={autoComplete}
        className="w-full rounded-lg border border-border-subtle bg-black/20 px-4 py-3 font-mono text-sm leading-5 text-text-main outline-none transition placeholder:text-white/25 focus:border-primary-container focus:ring-2 focus:ring-primary-container/20"
        id={name}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
      {helpText ? (
        <p className="text-xs leading-4 text-text-muted" id={hintId}>
          {helpText}
        </p>
      ) : null}
      {error ? (
        <p className="font-mono text-xs leading-4 text-error" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

type AlertProps = Readonly<{
  tone?: "error" | "warning";
  children: React.ReactNode;
}>;

export function Alert({ children, tone = "error" }: AlertProps) {
  const classes =
    tone === "warning"
      ? "border-warning bg-warning/10 text-text-main"
      : "border-error bg-error-container text-on-error-container";

  return (
    <div
      className={`rounded-r-lg border-l-2 px-3 py-2 text-sm leading-5 ${classes}`}
    >
      {children}
    </div>
  );
}

export function SubmitButton({
  children,
  disabled = false,
  isPending,
}: Readonly<{
  children: React.ReactNode;
  disabled?: boolean;
  isPending: boolean;
}>) {
  return (
    <button
      className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-primary-container px-4 py-3.5 text-[13px] font-bold leading-4 text-on-primary shadow-[0_0_20px_rgba(34,211,238,0.24)] transition hover:bg-primary hover:shadow-[0_0_26px_rgba(34,211,238,0.34)] focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:pointer-events-none disabled:opacity-60"
      disabled={disabled || isPending}
      type="submit"
    >
      {isPending ? "Working" : children}
    </button>
  );
}
