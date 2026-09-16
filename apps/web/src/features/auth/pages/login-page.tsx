import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import {
  ApiError,
  getSetupStatus,
  type SetupStatus,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AuthLayout } from "../../../app/layouts/auth-layout";
import { Alert, Field, SubmitButton } from "./auth-form-controls";
import { authCopy } from "../copy";

const loginSchema = z.object({
  email: z.string().trim().min(1, "Email is required."),
  password: z.string().min(1, "Password is required."),
});

type LoginForm = z.infer<typeof loginSchema>;

function messageFor(error: unknown) {
  if (error instanceof ApiError) {
    return (
      authCopy.errors[error.body.code as keyof typeof authCopy.errors] ??
      authCopy.errors.default
    );
  }
  return authCopy.errors.default;
}

export function LoginPage() {
  const navigate = useNavigate();
  const { signIn } = useAuthSession();
  const [formError, setFormError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    defaultValues: { email: "", password: "" },
    resolver: zodResolver(loginSchema),
  });

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        setSetupStatus(status);
        if (!status.hasDefaultWorkspace) {
          setSetupError(authCopy.errors.setup);
        }
      })
      .catch(() => setSetupError(authCopy.errors.REQUEST_FAILED));
  }, []);

  async function onSubmit(form: LoginForm) {
    setFormError(null);
    try {
      await signIn(form);
      navigate("/overview", { replace: true });
    } catch (error) {
      setFormError(messageFor(error));
    }
  }

  const registrationAllowed = setupStatus?.allowSignup ?? true;

  return (
    <AuthLayout
      description={authCopy.login.description}
      footerText={authCopy.login.footer}
      title={authCopy.login.title}
    >
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={handleSubmit(onSubmit)}
      >
        {setupError ? <Alert>{setupError}</Alert> : null}
        {formError ? <Alert>{formError}</Alert> : null}
        <Controller
          control={control}
          name="email"
          render={({ field }) => (
            <Field
              autoComplete="email"
              error={errors.email?.message}
              label="Email"
              name={field.name}
              onChange={field.onChange}
              placeholder="engineer@company.com"
              type="email"
              value={field.value}
            />
          )}
        />
        <Controller
          control={control}
          name="password"
          render={({ field }) => (
            <Field
              autoComplete="current-password"
              error={errors.password?.message}
              label="Password"
              name={field.name}
              onChange={field.onChange}
              placeholder="Password"
              type="password"
              value={field.value}
            />
          )}
        />
        <SubmitButton isPending={isSubmitting}>
          {authCopy.login.submit}
        </SubmitButton>
      </form>
      <div className="mt-8 border-t border-white/5 pt-5 text-center text-sm leading-5 text-text-muted">
        {registrationAllowed ? (
          <Link
            className="font-semibold text-primary-container transition hover:text-primary"
            to="/register"
          >
            Create an account
          </Link>
        ) : (
          <span>
            Account creation is disabled. Contact an administrator for access.
          </span>
        )}
      </div>
    </AuthLayout>
  );
}
