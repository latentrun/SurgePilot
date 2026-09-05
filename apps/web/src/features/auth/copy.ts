export const authCopy = {
  login: {
    title: "Sign in",
    description: "Continue to your SurgePilot workspace.",
    submit: "Sign in",
    footer: "Secure local access",
  },
  register: {
    firstAdminTitle: "Create administrator",
    firstAdminSubmit: "Create administrator",
    selfTitle: "Create account",
    selfSubmit: "Create account",
    firstAdminDescription:
      "Set up the first administrator for this SurgePilot workspace.",
    selfDescription: "Create an account to use SurgePilot in your workspace.",
    footer: "Secure local access",
    passwordHelp:
      "Use at least 10 characters with at least one letter and one number.",
  },
  errors: {
    EMAIL_ALREADY_EXISTS: "This email is already registered. Sign in instead.",
    INVALID_CREDENTIALS: "Email or password is incorrect.",
    PASSWORD_POLICY_VIOLATION:
      "Password must have at least 10 characters, one letter, and one number.",
    SIGNUP_DISABLED:
      "Account creation is disabled. Contact an administrator for access.",
    REQUEST_FAILED:
      "SurgePilot service is temporarily unavailable. Try again in a moment.",
    default: "Something went wrong. Try again.",
    setup:
      "Workspace setup is not complete. Contact an administrator before continuing.",
  },
} as const;
