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

export function LoginPage() {
  const { signIn } = useAuthSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        setSetupStatus(status);
        if (!status.hasDefaultWorkspace) setSetupError(authCopy.errors.setup);
      })
      .catch(() => setSetupError(authCopy.errors.REQUEST_FAILED));
  }, []);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!email.trim() || !password) {
      setFormError("Email and password are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await signIn({ email: email.trim(), password });
      window.history.replaceState({}, "", "/overview");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch (error) {
      setFormError(messageFor(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  const registrationAllowed = setupStatus?.allowSignup ?? true;

  return (
    <AuthLayout description={authCopy.login.description} footerText={authCopy.login.footer} title={authCopy.login.title}>
      <form noValidate onSubmit={onSubmit}>
        {setupError ? <Alert>{setupError}</Alert> : null}
        {formError ? <Alert>{formError}</Alert> : null}
        <Field autoComplete="email" label="Email" name="email" onChange={setEmail} placeholder="engineer@company.com" type="email" value={email} />
        <Field autoComplete="current-password" label="Password" name="password" onChange={setPassword} placeholder="Password" type="password" value={password} />
        <SubmitButton isPending={isSubmitting}>{authCopy.login.submit}</SubmitButton>
      </form>
      <div>
        {registrationAllowed ? <a href="/register">Create an account</a> : <span>Account creation is disabled. Contact an administrator for access.</span>}
      </div>
    </AuthLayout>
  );
}
