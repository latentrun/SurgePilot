# 08. Frontend Routing and UI Rules

## Stack and ownership

Web uses React, Vite, TypeScript, React Router route objects, TanStack Query, Tailwind CSS with CSS variables, React Hook Form, and Zod. Source-owned primitives live under `components/ui`; native HTML is preferred and focused interaction primitives may be added only when necessary.

Feature folders own routes, pages, queries, mutations, forms, and copy. The app layer owns the router, layouts, auth bootstrap, query client, generated API client wrapper, and Workspace/CSRF header handling. Router loaders are limited to authentication, authorization, redirect, and light route metadata; TanStack Query owns business data.

## Initial route inventory

```text
/login
/register
/overview
/scenarios
/scenarios/:scenarioId
/test-plans
/test-plans/:planId
/runs
/runs/:runId
/assets/env-groups
/assets/dependency-files
/resources/load-nodes
/resources/load-nodes/new
/admin/setup-status
```

Protected routes redirect unauthenticated users to login. Authenticated users are gated by backend-confirmed identity and role. Unknown routes render a Not Found state. Excluded future capability has no clickable navigation, placeholder page, or hidden route.

## API and state rules

Business calls use generated contracts. The client sends credentials automatically, attaches `x-csrf-token` to session-authenticated writes, and attaches the resolved `x-workspace-id` to Workspace-aware routes. It does not hand-convert snake/camel fields or infer permissions from the current page.

Every list and detail view provides loading, empty, error, and retry behavior. Mutations prevent duplicate submission and keep controls disabled until outcome is known. Filters and pagination that users may share belong in URL query state.

Run Report polling follows API state and stops in a terminal state. The page presents lifecycle, SLA verdict, and validity separately, with verdict and failure diagnosis before raw artifacts.

## UX and accessibility

Initial user-facing copy is English and centralized by feature. Forms use persistent labels, field-level validation, error summaries when useful, visible keyboard focus, and accessible names. Tables remain operable without pointer input. Status never relies on color alone, and background refreshes do not steal focus.

Visual implementation follows the root `DESIGN.md` baseline while correctness, contrast, and operational readability take precedence over decorative effects.
