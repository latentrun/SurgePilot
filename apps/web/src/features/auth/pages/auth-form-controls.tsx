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
    <div>
      <label htmlFor={name}>{label}</label>
      <input
        aria-describedby={describedBy || undefined}
        aria-invalid={error ? "true" : undefined}
        autoComplete={autoComplete}
        id={name}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
      {helpText ? <p id={hintId}>{helpText}</p> : null}
      {error ? <p id={errorId}>{error}</p> : null}
    </div>
  );
}

export function Alert({
  children,
  tone: _tone = "error",
}: Readonly<{ children: React.ReactNode; tone?: "error" | "warning" }>) {
  return <div role="alert">{children}</div>;
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
    <button disabled={disabled || isPending} type="submit">
      {isPending ? "Working…" : children}
    </button>
  );
}
