import { useEffect, useState } from "react";

import {
  ApiError,
  getSetupStatus,
  type SetupStatus,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AuthLayout } from "../../../app/layouts/auth-layout";
import { Alert, Field, SubmitButton } from "./auth-form-controls";
import { authCopy } from "../copy";

function messageFor(error: unknown) {
  if (error instanceof ApiError) {
    return authCopy.errors[error.body.code as keyof typeof authCopy.errors] ?? authCopy.errors.default;
  }
  return authCopy.errors.default;
}

export function RegisterPage() {
  const { signUp } = useAuthSession();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        setSetupStatus(status);
        if (!status.hasDefaultWorkspace) setSetupError(authCopy.errors.setup);
      })
      .catch(() => setSetupError(authCopy.errors.REQUEST_FAILED));
  }, []);

  function validate() {
    const next: Record<string, string> = {};
    if (!displayName.trim()) next.displayName = "Display name is required.";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) next.email = "Enter a valid email address.";
    if (password.length < 10 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      next.password = authCopy.errors.PASSWORD_POLICY_VIOLATION;
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!validate() || !canRegister) return;
    setIsSubmitting(true);
    try {
      await signUp({ displayName: displayName.trim(), email: email.trim(), password });
      window.history.replaceState({}, "", "/overview");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch (error) {
      if (error instanceof ApiError) {
        const serverFields: Record<string, string> = {};
        for (const detail of error.body.details ?? []) {
          if (detail.field) serverFields[detail.field] = detail.message ?? "Check this field and try again.";
        }
        if (error.body.code === "PASSWORD_POLICY_VIOLATION") serverFields.password = authCopy.errors.PASSWORD_POLICY_VIOLATION;
        setFieldErrors(serverFields);
      }
      setFormError(messageFor(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  const canRegister = setupStatus?.allowSignup ?? true;
  const firstAdmin = setupStatus?.needsBootstrap === true;

  return (
    <AuthLayout description={firstAdmin ? authCopy.register.firstAdminDescription : authCopy.register.selfDescription} footerText={authCopy.register.footer} title={firstAdmin ? authCopy.register.firstAdminTitle : authCopy.register.selfTitle}>
      <form noValidate onSubmit={onSubmit}>
        {setupError ? <Alert>{setupError}</Alert> : null}
        {!canRegister ? <Alert>{authCopy.errors.SIGNUP_DISABLED}</Alert> : null}
        {formError ? <Alert>{formError}</Alert> : null}
        <Field autoComplete="email" error={fieldErrors.email} label="Email" name="email" onChange={setEmail} placeholder="engineer@company.com" type="email" value={email} />
        <Field autoComplete="name" error={fieldErrors.displayName} label="Display name" name="displayName" onChange={setDisplayName} placeholder="Alex Chen" type="text" value={displayName} />
        <Field autoComplete="new-password" error={fieldErrors.password} helpText={authCopy.register.passwordHelp} label="Password" name="password" onChange={setPassword} placeholder="Password" type="password" value={password} />
        <SubmitButton disabled={!canRegister} isPending={isSubmitting}>{firstAdmin ? authCopy.register.firstAdminSubmit : authCopy.register.selfSubmit}</SubmitButton>
      </form>
      <div><a href="/login">Already have an account? Sign in</a></div>
    </AuthLayout>
  );
}
