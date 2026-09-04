# 06. Security, Permission, and Workspace

## Identity baseline

The initial product uses local email/password accounts. The first successful registration becomes `admin`; later registrations become `user` when signup is enabled. Email is normalized and globally unique. Passwords use Argon2id and are never returned or logged.

Sessions are server-side PostgreSQL records. The browser receives an HttpOnly session cookie and session-bound CSRF token. Logout invalidates the current session. Login failures use one public error regardless of whether the account is absent, locked, or has a wrong password; account-level failure tracking provides the initial brute-force guard.

## Authorization

Authorization is enforced by the API, never by hidden UI alone. `admin` can perform platform administration and normal business actions; `user` can perform allowed Workspace business actions. Destructive and execution-control actions produce minimal audit events without secret values.

## Workspace rules

Users belong to Workspaces through membership records. Initial registration adds the user to the Default Workspace. Workspace-aware APIs resolve `x-workspace-id` or the user's Default Workspace and apply the filter in every read and write query.

Scenario, Test Plan, Run, Run Snapshot, Env Group, Dependency File, Artifact metadata, and Private Load Node are Workspace-owned. Public Load Nodes are platform-owned; visibility and use still require authorization. Admin Setup Status is platform-level and read-only. Neither exception permits unscoped access to ordinary business records.

Cross-Workspace references return not found or forbidden without leaking record existence. Run creation verifies that every referenced asset is visible in the same effective Workspace.

## Credentials and secrets

Private Load Node SSH credentials are write-only and encrypted with AES-256-GCM using a deployment-provided key. Runner internal tokens are separate from browser sessions and bound to Runner identity. Session IDs, CSRF tokens, passwords, password hashes, SSH material, Runner tokens, MinIO credentials, and environment secrets must not enter API responses, audit detail, generated contracts, or normal logs.

The initial milestone does not implement SSO, password email flows, user-management UI, Workspace switching/membership UI, PostgreSQL RLS, external rate limiting, secret Env Groups, credential rotation, or a general secret-management framework.
