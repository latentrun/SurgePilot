import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import {
  ApiError,
  getSetupStatus,
  type ApiErrorBody,
  type SetupStatus,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AuthLayout } from "../../../app/layouts/auth-layout";
import { Alert, Field, SubmitButton } from "./auth-form-controls";
import { authCopy } from "../copy";

const passwordPolicyMessage =
  "Use at least 10 characters with a letter and a number.";

const registerSchema = z.object({
  displayName: z
    .string()
    .trim()
    .min(1, "Display name is required.")
    .max(120, "Display name is too long."),
  email: z.string().trim().email("Enter a valid email address."),
  password: z
    .string()
    .min(10, passwordPolicyMessage)
    .regex(/[A-Za-z]/, passwordPolicyMessage)
    .regex(/[0-9]/, passwordPolicyMessage),
});

type RegisterForm = z.infer<typeof registerSchema>;

type FieldErrors = Partial<Record<keyof RegisterForm, string>>;

function fieldErrorMessage(field: string) {
  if (field === "email") {
    return "Enter a valid email address.";
  }
  if (field === "password") {
    return authCopy.errors.PASSWORD_POLICY_VIOLATION;
  }
  if (field === "displayName") {
    return "Check the display name and try again.";
  }
  return "Check this field and try again.";
}

function fieldErrorsFromError(body: ApiErrorBody): FieldErrors {
  const errors: FieldErrors = {};
  for (const detail of body.details ?? []) {
    if (
      detail.field === "displayName" ||
      detail.field === "email" ||
      detail.field === "password"
    ) {
      errors[detail.field] = fieldErrorMessage(detail.field);
    }
  }
  if (body.code === "PASSWORD_POLICY_VIOLATION") {
    errors.password = authCopy.errors.PASSWORD_POLICY_VIOLATION;
  }
  return errors;
}

function messageFor(error: unknown) {
  if (error instanceof ApiError) {
    return (
      authCopy.errors[error.body.code as keyof typeof authCopy.errors] ??
      authCopy.errors.default
    );
  }
  return authCopy.errors.default;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { signUp } = useAuthSession();
  const [formError, setFormError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const {
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    defaultValues: { displayName: "", email: "", password: "" },
    resolver: zodResolver(registerSchema),
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

  const copy = useMemo(() => {
    if (setupStatus?.needsBootstrap) {
      return {
        title: authCopy.register.firstAdminTitle,
        description: authCopy.register.firstAdminDescription,
        submit: authCopy.register.firstAdminSubmit,
      };
    }
    return {
      title: authCopy.register.selfTitle,
      description: authCopy.register.selfDescription,
      submit: authCopy.register.selfSubmit,
    };
  }, [setupStatus?.needsBootstrap]);

  async function onSubmit(form: RegisterForm) {
    setFormError(null);
    try {
      await signUp(form);
      navigate("/overview", { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        const fieldErrors = fieldErrorsFromError(error.body);
        for (const [field, message] of Object.entries(fieldErrors)) {
          setError(field as keyof RegisterForm, { message, type: "server" });
        }
      }
      setFormError(messageFor(error));
    }
  }

  const canRegister = setupStatus?.allowSignup ?? true;

  return (
    <AuthLayout
      description={copy.description}
      footerText={authCopy.register.footer}
      title={copy.title}
    >
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={handleSubmit(onSubmit)}
      >
        {setupError ? <Alert>{setupError}</Alert> : null}
        {!canRegister ? <Alert>{authCopy.errors.SIGNUP_DISABLED}</Alert> : null}
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
          name="displayName"
          render={({ field }) => (
            <Field
              autoComplete="name"
              error={errors.displayName?.message}
              label="Display name"
              name={field.name}
              onChange={field.onChange}
              placeholder="Alex Chen"
              type="text"
              value={field.value}
            />
          )}
        />
        <Controller
          control={control}
          name="password"
          render={({ field }) => (
            <Field
              autoComplete="new-password"
              error={errors.password?.message}
              helpText={authCopy.register.passwordHelp}
              label="Password"
              name={field.name}
              onChange={field.onChange}
              placeholder="Password"
              type="password"
              value={field.value}
            />
          )}
        />
        <SubmitButton disabled={!canRegister} isPending={isSubmitting}>
          {copy.submit}
        </SubmitButton>
      </form>
      <div className="mt-5 border-t border-white/5 pt-5 text-center text-sm leading-5 text-text-muted">
        <Link
          className="font-semibold text-primary-container transition hover:text-primary"
          to="/login"
        >
          Already have an account? Sign in
        </Link>
      </div>
    </AuthLayout>
  );
}
