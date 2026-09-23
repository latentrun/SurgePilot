# 08 Frontend Routing and UI Rules

- Documentation status: Draft v1
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Security and Workspace Source: `docs/sdd/06-security-permission-workspace.md`
- Current delivery target: P0 baseline + accepted P1/P2 slices; ADR-0013 authorizes the static Marketing Landing and Logo, amended only by ADR-0026/P2-07 for exact public Docs/repository targets and truthful presentation labels
- Scope of application: Frontend routing, layouts, UI stack, source-owned primitives, copy, query state, auth gate, Workspace / CSRF header injection, Run Report polling, AI Coding, code review

---

## 1. Purpose

This article defines SurgePilot P0 front-end routing, layout, UI stack, component boundaries, data acquisition, permission interception, status display, copywriting and polling rules.

This article serves three goals:

1. When multiple Slices are developed in parallel, the front-end directory, routing, data acquisition and page status do not diverge;
2. Let AI Coding know clearly which UI can and cannot be written, which dependencies can be introduced, and which dependencies are prohibited from being introduced;
3. Ensure that the Web strictly adheres to P0 Scope, contracts, Workspace, CSRF, security and Run state convergence boundaries.

This article is not a complete visual design draft, nor is it a complete component library document. Page-level interaction details are still defined by the corresponding P0 Slice SDD, but must not violate the global rules of this article.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This article relies on:

1. `docs/prd/PRD.md`: Product source of product scope, page path, information architecture, status and experience principles;
2. `docs/sdd/00-product-scope-and-priority.md`: P0/P1/P2 scope gate;
3. `docs/sdd/01-architecture-overview.md`: Web/API/Runner boundary, contracts-first, P0 technology stack;
4. `docs/sdd/02-repo-structure-and-dev-workflow.md`: monorepo, `apps/web` directory, AI Coding and verify rules;
5. `docs/sdd/04-api-contract-guidelines.md`: API URL, OpenAPI, error shape, headers, pagination, filtering, sorting;
6. `docs/sdd/06-security-permission-workspace.md`: session, CSRF, role, Workspace, permissions and sensitive information rules;
7. `docs/sdd/09-testing-and-acceptance-strategy.md`: Front-end testing and acceptance strategy;
8. `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`: P2 static Marketing Landing and Logo authorized source.
9. `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`: P2 authenticated Help AI Agents route and skill download authorization source.
10. `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`: exact public Landing Docs/repository targets, truthful presentation labels, and separate Pages visual-parity authorization source.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this document conflicts with the PRD product scope, PRD shall prevail and revise this document.
2. If this article conflicts with 00 Scope Gate, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with API URLs, headers, error shapes, pagination or OpenAPI rules of 04, 04 will prevail and this article will be revised.
4. If this article conflicts with the session, CSRF, role, Workspace or permission rules of 06, 06 shall prevail and this article shall be revised.
5. Slice SDD can refine pages, fields, forms, error codes, and tests, but it must not bypass the global front-end boundaries of this article.
6. Code implementation must not override the rules of this article on the grounds that "the page is already written like this", "AI is easier to generate", "hidden entrance", "will be deleted later".
7. If the front-end UI stack, interface language or routing strategy is changed in the future, PRD, this article, 01, 02, `apps/web/AGENTS.md` and related dependencies must be updated simultaneously.

### 2.3 Decision Basis and Alignment

P0 frontend language follows `docs/prd/PRD.md` §6.2.1.

P0 frontend UI stack is defined by this document and reflected in:

- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `apps/web/AGENTS.md`

If the frontend UI stack, interface language, or routing strategy changes later, update all affected documents in the same change.

---

## 3. Confirmed Frontend Decisions

| Area | Decision |
| --- | --- |
| Frontend app | React + Vite + TypeScript |
| Routing | React Router `createBrowserRouter` + nested route objects |
| Route ownership | Feature-based route modules |
| Route code splitting | React Router route `lazy` modules |
| Business data fetching | TanStack Query |
| Router loader usage | Auth bootstrap, auth gate, role gate, redirect, lightweight route metadata only |
| Visual system | Tailwind CSS + CSS variables |
| UI primitives | Source-owned minimal primitives under `apps/web/src/components/ui/*` |
| Interaction primitives | Radix UI only when native HTML is insufficient |
| Forms | React Hook Form + Zod |
| Tables | TanStack Table + source-owned `DataTable` shell |
| API client | Generated client/types from `@surgepilot/contracts` only |
| Auth | Cookie-based session; browser sends credentials automatically |
| CSRF | `x-csrf-token` on browser write requests after session exists |
| Workspace context | `x-workspace-id` header for workspace-aware business APIs |
| Copy and language | P0 frontend user-facing copy is English only; copy is centralized in copy files |
| i18n framework | Not introduced in P0 |
| P1/P2 navigation | Planned in docs only unless a named accepted Slice/ADR activates the route; ADR-0013 activates the static public `/` Marketing Landing and Logo, and ADR-0026/P2-07 adds only its exact public Docs/repository links |

---

## 4. Repository Structure for Web

Recommended `apps/web` structure:

```text
apps/web/
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   ├── route-guards.ts
│   │   ├── query-client.ts
│   │   ├── api-client.ts
│   │   ├── auth-session.ts
│   │   └── layouts/
│   │       ├── auth-layout.tsx
│   │       ├── app-layout.tsx
│   │       └── admin-section-layout.tsx
│   ├── components/
│   │   └── ui/
│   ├── copy/
│   │   └── global.ts
│   ├── features/
│   │   ├── marketing/          # ADR-0013 static Landing route only
│   │   └── <feature>/
│   │       ├── routes.tsx
│   │       ├── pages/
│   │       ├── components/
│   │       ├── queries.ts
│   │       ├── mutations.ts
│   │       ├── schemas.ts
│   │       └── copy.ts
│   ├── hooks/
│   ├── utils/
│   ├── index.css
│   └── main.tsx
├── public/
├── tests/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── AGENTS.md
```

Rules:

1. `app/` owns router, providers, query client, generated API client wrapping, auth session state, and layouts.
2. `features/<feature>/` owns feature routes, pages, feature components, copy, query hooks, mutation hooks and form schemas.
3. `components/ui/` contains only source-owned minimal primitives, not feature business components.
4. `hooks/` and `utils/` contain cross-feature utilities only when reuse is proven.
5. Business components must not be promoted to shared components until at least two features need them and their API is stable.

---

## 5. Routing Organization

### 5.1 Route Module Rule

Use feature-based route modules.

Each feature exports route objects from its own `routes.tsx`:

```tsx
export const scenarioRoutes = [
  {
    path: "scenarios",
    lazy: () => import("./pages/scenario-list-page"),
  },
  {
    path: "scenarios/:scenarioId",
    lazy: () => import("./pages/scenario-designer-page"),
  },
];
```

Root router only aggregates route objects:

```tsx
export const router = createBrowserRouter([
  ...authRoutes,
  {
    element: <AppLayout />,
    loader: requireAuth,
    children: [
      ...overviewRoutes,
      ...scenarioRoutes,
      ...testPlanRoutes,
      ...runRoutes,
      ...assetRoutes,
      ...resourceRoutes,
      ...adminRoutes,
    ],
  },
]);
```

Rules:

1. Use `createBrowserRouter`.
2. Use nested routes.
3. Use React Router route `lazy` modules for route-level code splitting.
4. Do not centralize all page imports in `app/router.tsx`.
5. Do not create routes for P1/P2 pages in P0 implementation.
6. A planned P1/P2 path may appear in docs, but it must not become a clickable route or rendered page in P0.

### 5.2 Loader Boundaries

Router loaders are allowed only for:

1. auth bootstrap;
2. auth gate;
3. role gate;
4. redirect;
5. lightweight route metadata.

Router loaders must not fetch:

1. normal list data;
2. detail data;
3. Run Report data;
4. form option data;
5. artifacts data.

Business data must use TanStack Query. This avoids split cache ownership between React Router loader data and TanStack Query.

### 5.3 P0 Route Inventory

P0 implemented routes:

| Page | Route | Layout | P0 rule |
| --- | --- | --- | --- |
| Landing | `/` | Marketing Landing | Public static route for unauthenticated visitors; authenticated visitors redirect to `/overview`; ADR-0013 only |
| Login | `/login` | AuthLayout | Public auth route |
| Register | `/register` | AuthLayout | Public auth route; first Admin bootstrap supported by API |
| Overview | `/overview` | AppLayout | Auth required |
| Scenarios | `/scenarios` | AppLayout | Auth required |
| Scenario Designer | `/scenarios/:scenarioId` | AppLayout | Auth required |
| Test Plans | `/test-plans` | AppLayout | Auth required |
| Test Plan Editor | `/test-plans/:planId` | AppLayout | Auth required; frontend route param follows PRD |
| Runs | `/runs` | AppLayout | Auth required |
| Run Report | `/runs/:runId` | AppLayout | Auth required |
| Env Groups | `/assets/env-groups` | AppLayout | Auth required |
| Dependency Files | `/assets/dependency-files` | AppLayout | Auth required |
| Load Nodes | `/resources/load-nodes` | AppLayout | Auth required |
| Register Load Node | `/resources/load-nodes/new` | AppLayout | Auth required |
| Admin Setup Status | `/admin/setup-status` | AppLayout + AdminSectionLayout | Admin required |

These are frontend route parameters. API path parameters are governed by `docs/sdd/04-api-contract-guidelines.md` and may use API-specific names such as `{testPlanId}`.

P0 redirects:

1. `/` redirects to `/overview` when authenticated.
2. `/` renders static Marketing Landing when unauthenticated.
3. Authenticated user visiting `/login` or `/register` redirects to `/overview`.
4. Login success redirects to `/overview`.
5. Register success redirects to `/overview`.
6. Logout success redirects to `/login`.
7. `/admin` redirects to `/admin/setup-status` for authenticated Admin users.
8. Unknown route renders Not Found.
9. Unauthenticated protected route redirects to `/login`.
10. Authenticated non-admin access to `/admin/*` renders a 403 page.

### 5.4 P1/P2 Routes Not Implemented in P0

The following routes are planned but must not be implemented as clickable UI in P0:

```text
/api-catalog
/api-catalog/:specId
/observability/monitoring
/help
/admin/users
/admin/system-settings
/admin/workspaces
```

Rules:

1. Do not add navigation entries for these routes in P0.
2. Do not create placeholder pages that look usable.
3. Do not add hidden routes that expose P1/P2 capabilities.
4. P0 docs may mention future routes only as roadmap or non-clickable planning.
5. `/help` is not implemented in the P0 baseline. ADR-0016/P2-04 separately activates it as an authenticated P2 route with the bounded Help AI Agents contract in §5.6.
6. `/admin` is not a standalone page in P0; it redirects to `/admin/setup-status` for Admin users.

---

### 5.5 P2 Static Marketing Landing Route

ADR-0013 authorizes only a static public Marketing Landing and Logo migration. Rules:

1. `/` must render the Marketing Landing only for unauthenticated visitors.
2. Authenticated `/` must redirect to `/overview` with `replace`.
3. `/overview` stays under `RequireAuth + AppLayout`; AppLayout Logo continues linking to `/overview`.
4. The Landing route must live in `apps/web/src/features/marketing/routes.tsx` and use React Router `lazy`; `app/router.tsx` may aggregate `...marketingRoutes` but must not directly import the Landing page.
5. Landing styles must be scoped under a marketing root class and must not mutate global product tokens.
6. Runtime design assets must be local. The page must not request Tailwind CDN, Google Fonts, Material Symbols, `lh3.googleusercontent.com`, or other remote Stitch assets.
7. Interactive links include `/login`, `/register`, in-page anchors, and—only through ADR-0026/P2-07—the exact public Docs and repository URLs. API Guide, Community, Security, and other items remain disabled unless separately authorized.
8. The original animated throughput/VU dashboard, Recent Test Runs, and Distributed load mesh are allowed only as adjacent, explicitly labelled UI demonstration/example data that is not a live service, live topology, or measured benchmark; they are never product evidence. `All systems operational` and hosted-status implications remain forbidden.
9. By explicit repository-owner decision, the Marketing Landing is desktop-Web-first and retains full CSS/SVG/counter motion without a Landing-scoped reduced-motion override.
10. This route does not authorize Help, API Guide, Community, hosted status, CMS, analytics, SDK, MCP, API, DB, migration, runner, contract or Load Node changes.

### 5.6 P2 Help AI Agents Route

ADR-0016/P2-04 authorizes authenticated `/help` under `RequireAuth + AppLayout`.

Rules:

1. The Help route is available to both `user` and `admin`; it is not an Admin-only page.
2. The exact tab order is `Getting Started`, `AI Agents`, `Scripting`, `API Catalog`, `Troubleshooting`, and `Limits & Activation`.
3. `Automation` is replaced by `AI Agents` and must not remain as a visible tab alias.
4. The AI Agents tab is limited to API Keys, explicit Workspace ID, Public API use, official skill source download, local user-owned agent consumption, operation allowlist, and write confirmation.
5. The Help download action uses the generated Web/business operation for `GET /api/v1/account/ai-skill/download` through the existing API-client wrapper/blob-download pattern.
6. The page must not claim SDK, MCP, marketplace, installer, built-in agent runtime, automatic Scenario generation, automatic tuning, or automatic report analysis.
7. `Limits & Activation` must distinguish the active SurgePilot-owned system OpenAPI lifecycle (first-Admin creation and later startup reconciliation of an existing asset) from inactive user/external automatic ingestion.
8. ADR-0013's unauthenticated Marketing Landing is amended only by ADR-0026/P2-07 for exact public Docs/repository links and truthful presentation labels; P2-04 does not activate API Guide, Community, SDK, MCP, marketplace, or other public targets.


## 6. Layouts

### 6.1 Layout Hierarchy

Use three product layout levels plus the ADR-0013 public Marketing Landing route:

```text
Marketing Landing
  / (unauthenticated only)

AuthLayout
  /login
  /register

AppLayout
  all authenticated business routes

AdminSectionLayout
  nested under AppLayout
  /admin/*
```

### 6.2 AuthLayout

AuthLayout responsibilities:

1. Render Login and Register pages.
2. Show product name and short product positioning.
3. Show no global navigation.
4. Show no Workspace selector or Workspace display.
5. Avoid loading authenticated business data.

### 6.3 AppLayout

AppLayout responsibilities:

1. Render global navigation.
2. Render top bar.
3. Render current user summary.
4. Render read-only Default Workspace name.
5. Render page outlet.
6. Provide global error boundary where appropriate.

Rules:

1. Do not implement Workspace switcher in P0.
2. Do not show P1/P2 navigation entries.
3. Navigation must use PRD product terms: Overview, Scenarios, Test Plans, Runs, Assets, Resources, Admin.
4. Help may be linked only when an accepted Slice implements a real Help page. ADR-0016/P2-04 activates the authenticated AppLayout Help entry; it does not activate public Marketing Landing documentation links.

### 6.4 AdminSectionLayout

AdminSectionLayout responsibilities:

1. Nest under AppLayout.
2. Render Admin section title and description.
3. Render Admin section outlet.
4. Optionally provide Admin-local error boundary.

Rules:

1. P0 has no standalone Admin shell.
2. P0 Admin reuses global navigation.
3. P0 Admin only exposes Setup Status.
4. Do not show Users, Workspace Management or System Settings navigation in P0.

### 6.5 Error Boundaries and Route Lazy Fallbacks

Rules:

1. AppLayout should provide one root error boundary for authenticated shell failures.
2. Each route module should define its own `errorElement` or equivalent route-level error boundary so a page failure does not blank the entire authenticated app.
3. AdminSectionLayout may add an Admin-local error boundary, but it must not replace route module boundaries.
4. Business data requests must use TanStack Query loading, error and empty states; do not use Suspense for normal API data fetching in P0.
5. React Router route `lazy` fallback should be handled at the layout level or route-shell level.
6. Do not implement a single root-only boundary as the only frontend error handling layer.

---

## 7. UI Stack and Styling

### 7.1 Visual System Decision

P0 uses a single visual system:

```text
Tailwind CSS + CSS variables + source-owned minimal primitives
```

P0 does not use a third-party visual component system.

### 7.2 Allowed Dependencies

Allowed UI and utility dependencies:

```text
Tailwind CSS
Radix UI packages as needed
React Hook Form
Zod
@hookform/resolvers
TanStack Table
TanStack Query
React Router
clsx
tailwind-merge
class-variance-authority
lucide-react
```

Rules:

1. Radix packages must be installed only when the active Slice needs the specific interaction primitive.
2. Import `lucide-react` icons individually.
3. Use `clsx` for conditional class names.
4. Use `tailwind-merge` to resolve conflicting Tailwind classes in reusable primitives.
5. Use `class-variance-authority` only for controlled variants in `components/ui/*` or stable reusable display components.

### 7.3 Forbidden Dependencies and Patterns

Forbidden visual component systems:

```text
Ant Design
MUI
Chakra UI
Arco Design
Mantine
Bootstrap component system
DaisyUI
Any other visual component system unless approved by ADR
```

Forbidden patterns:

1. AntD + Tailwind dual stack.
2. Multiple visual systems in the same frontend app.
3. Global CSS overrides against third-party component internals.
4. Building a general-purpose internal design system platform in P0.
5. Creating reusable UI primitives not needed by the current P0 Slice.
6. Adding clickable P1/P2 UI entry points during P0.
7. Introducing `classnames`, `styled-components`, `@emotion/*`, `stitches` or equivalent styling tools without ADR.
8. Introducing a second icon library.

### 7.4 CSS and Token Rules

File responsibilities:

```text
apps/web/src/index.css
  - Tailwind directives
  - CSS variables
  - minimal body reset only
  - no third-party component override

apps/web/tailwind.config.js
  - content includes src/**/*.{ts,tsx}
  - map theme tokens to CSS variables where needed

apps/web/src/components/ui/*
  - use clsx / tailwind-merge / cva
  - no global CSS dependency
```

Rules:

1. Colors, radius, spacing and shadows must come from Tailwind tokens or CSS variables.
2. Do not use hard-coded hex values in pages. If a one-off value is required, it must be moved into a token first.
3. Do not add a second theme provider.
4. Do not use `!important` to fight component styles.
5. `components/ui/*` must expose `className` where composition requires it, but must not expose an overly broad styling API.
6. P0 is light mode only.
7. P0 is desktop-first.
8. Tokens may reserve names for future dark mode, tablet or mobile adaptation, but P0 must not implement user-visible dark mode, mobile-specific layouts or tablet-specific layouts unless a P0 Slice explicitly requires it.
9. Do not add `dark:` Tailwind variants in P0 product UI.

---

## 8. Source-Owned UI Primitives

### 8.1 Boundary

`apps/web/src/components/ui/*` contains only source-owned minimal primitives.

It is not a cross-project design system. It must not become a general-purpose component platform.

Allowed examples:

```text
apps/web/src/components/ui/button.tsx
apps/web/src/components/ui/input.tsx
apps/web/src/components/ui/textarea.tsx
apps/web/src/components/ui/dialog.tsx
apps/web/src/components/ui/tabs.tsx
apps/web/src/components/ui/badge.tsx
apps/web/src/components/ui/empty-state.tsx
apps/web/src/components/ui/error-state.tsx
apps/web/src/components/ui/page-header.tsx
```

Forbidden in `components/ui/*`:

1. Feature-specific business components.
2. Test Plan Editor-specific components.
3. Run Report-specific business sections.
4. ProTable, AdvancedTable or Dashboard framework.
5. Generic layout framework beyond current P0 need.

Business components belong under:

```text
apps/web/src/features/<feature>/components/
```

### 8.2 M0 / P0-00 Starting Set

M0 / P0-00 may implement only these primitives:

```text
1. Button
2. Input
3. Textarea
4. Dialog
5. Tabs
6. Badge
7. EmptyState
8. ErrorState
9. PageHeader
```

Rules:

1. `Select` is not part of the starting set.
2. If M0 / P0-00 needs a simple selection field, use native `<select>` locally.
3. Add a Radix-based Select or Combobox only when a Slice needs search, async loading, keyboard navigation or richer aria behavior.

### 8.3 Incremental Additions by Slice

Recommended additions:

```text
P0-01 Env Groups:
  - Select
  - DataTable
  - ConfirmDialog

P0-03 Load Nodes:
  - StatusBadge
  - FormField

P0-05 Visual Scenario / Debug Run:
  - FieldArraySection
  - InlineError

P0-06 Test Plan / Run Now:
  - FieldArraySection reuse
  - InlineError reuse
  - ScenarioOrchestrationEditor
  - SlaRuleEditor

P0-07 Run Report / Artifacts / Validity:
  - KpiCard
  - ReportSection
  - ArtifactList

P0-08 Overview / P0 Polish:
  - polish existing components only
  - do not add broad new primitive categories
```

Rules:

1. Add primitives only when required by the active Slice.
2. Prefer local feature components first when reuse is not proven.
3. Promote to shared UI only when the component is generic, stable and needed across features.

### 8.4 DataTable Shell Boundary

`DataTable` uses TanStack Table and remains intentionally small.

Allowed responsibilities:

```text
- Column definitions to table rendering
- Pagination
- URL query sync for page / pageSize / cursor / limit / simple filter
- Loading / empty / error states
- Row hover state
- Optional row click
- Simple text filter input
```

Forbidden responsibilities:

```text
- Column drag-and-drop ordering
- Frozen columns
- Virtual scrolling
- Advanced multi-column filter popovers
- Inline editing
- Excel / CSV export
- Persistent column settings
- Saved views
- User-customizable density settings
- ProTable-like toolbar framework
```

Rules:

1. Multi-column filters, if needed, must be implemented in the specific page, not in `DataTable` core.
2. `DataTable` is a reusable list shell, not an internal ProTable.
3. `DataTable` must support EmptyState, ErrorState and LoadingSkeleton integration.

---

## 9. Forms

P0 forms use:

```text
React Hook Form + Zod
```

Rules:

1. Complex forms must have a Zod schema.
2. Cross-field validation belongs in schema `refine`, `superRefine` or a clear form-level validation function.
3. Dynamic arrays use `useFieldArray`.
4. Submit actions must prevent duplicate submission.
5. Field-level errors must be displayed near the relevant field.
6. Form-level errors must use ErrorState or an equivalent inline error block.
7. API request and response types must come from generated contracts.
8. Do not hand-write API request or response types in Web.
9. Do not parse API `message` as business logic.
10. Map stable `code` and `details[].code` to frontend copy.

---

## 10. Accessibility

Use native HTML when it is sufficient. Use Radix UI when interaction behavior requires focus management, keyboard navigation, dismissal behavior or aria semantics.

Components that must use Radix or an equivalent approved accessible primitive:

```text
Dialog
Popover
Tabs
Complex Select
Combobox
Menu-like interactions
```

Rules:

1. Do not hand-write focus trap logic for dialogs.
2. Do not hand-write complex keyboard navigation for menu-like controls.
3. Dialogs must have accessible title and description.
4. Form fields must have labels or accessible names.
5. Error text must be associated with fields where applicable.
6. Loading states must not trap keyboard focus.
7. Destructive actions must require a confirmation pattern.

---

## 11. API Client, Auth, Workspace and CSRF

### 11.1 API Client Boundary

Web calls API only through generated contracts from `@surgepilot/contracts`.

Rules:

1. Do not hand-write API response/request types.
2. Do not import generated files through relative paths into `packages/contracts/generated/...`.
3. Do not call PostgreSQL, MinIO, Load Nodes or runner internal endpoints from Web.
4. Do not expose MinIO credentials, object keys, runner token, session token or credential values to Web.
5. Web must use browser credentials for API calls.

### 11.2 Identity Bootstrap

Identity bootstrap API:

```http
GET /api/v1/auth/me
```

It returns:

1. current user identity;
2. role;
3. Workspace context derived from P0 membership;
4. no `csrfToken`;
5. no session token;
6. no password hash;
7. no credential or secret.

Rules:

1. Current-user API does not consume `x-workspace-id`.
2. Current-user API does not require business Workspace resolution.
3. If response includes `defaultWorkspaceId`, it must be a derived convenience field from the user's P0 Workspace membership, not a second source of truth such as `users.default_workspace_id`.
4. Prefer returning a Workspace object when the Slice defines it, for example `workspace: { id, name }`.

### 11.3 CSRF Retrieval

CSRF retrieval API:

```http
GET /api/v1/auth/csrf
```

Rules:

1. Requires existing valid session.
2. Returns `csrfToken`.
3. Frontend stores CSRF token in JS memory only.
4. Do not store CSRF token in `localStorage` or `sessionStorage`.
5. Do not log, snapshot or expose CSRF token.
6. Page refresh may recover CSRF token through this endpoint.

### 11.4 Login and Register

Rules:

1. Login and register are pre-session auth endpoints and are CSRF-exempt.
2. Login and register success may return `csrfToken` to save one round trip.
3. Login and register responses must not return session cookie value in JSON.
4. Browser receives session through `Set-Cookie` only.

### 11.5 Header Injection Middleware

API middleware rules:

1. Use browser credentials for API calls.
2. Inject `x-workspace-id` only for authenticated workspace-aware business APIs.
3. Inject `x-csrf-token` only for write methods when token exists.
4. Do not inject CSRF token for `GET`, `HEAD` or `OPTIONS`.
5. Do not inject Workspace header for auth bootstrap, CSRF retrieval, health, readiness or platform-level setup checks.
6. Do not inject any runner internal token from Web.

Workspace header skip cases:

```text
auth login
auth register
auth current user
auth csrf
health
readiness
platform-level setup status
```

CSRF skip cases:

```text
GET
HEAD
OPTIONS
register
login
first-admin bootstrap
internal runner endpoints
health
readiness
```

Logout is a write request after session exists. It should require CSRF unless the Auth Slice explicitly defines a safe exception.

### 11.6 Route Gates

Route gate rules:

1. Unauthenticated `/` renders the ADR-0013 Marketing Landing; unauthenticated protected route access redirects to `/login`.
2. Authenticated user visiting `/login` or `/register` redirects to `/overview`.
3. Login success redirects to `/overview`.
4. Register success redirects to `/overview`.
5. Logout success redirects to `/login`.
6. Authenticated Admin visiting `/admin` redirects to `/admin/setup-status`.
7. Authenticated non-admin access to `/admin/*` renders a 403 page.
8. Frontend may hide unauthorized navigation entries.
9. Backend authorization remains the final authority.
10. Do not rely on frontend route visibility for security.

---

## 12. Language and Copy

### 12.1 Copy and Language Decision

PRD §6.2.1 defines P0 frontend as English-only user-facing copy.

P0 frontend does not introduce an i18n framework.

Rules:

1. Do not introduce an i18n framework in P0.
2. User-facing frontend copy must be English in P0.
3. Do not add Chinese UI copy.
4. Do not add locale switcher.
5. Do not prepare hidden locale bundles.
6. User-visible copy must be centralized in copy files.
7. API `message` is English fallback only, not an i18n key.
8. Frontend UX copy must be mapped from stable error `code` and `details[].code`.
9. Do not parse API `message` text as frontend logic.

### 12.2 Copy File Structure

```text
apps/web/src/copy/global.ts
apps/web/src/features/<feature>/copy.ts
```

Rules:

1. User-visible strings must come from copy files.
2. Debug-only labels may be inline if they are not user-facing.
3. Test IDs must not be used as user-facing copy.
4. API messages must not be parsed as business or UX logic.
5. Feature copy should stay close to the feature.
6. Common copy may be promoted to `src/copy/global.ts` only when reused across features.

Example:

```ts
export const authCopy = {
  loginTitle: "Sign in to SurgePilot",
  loginSubtitle: "Use your local account to continue.",
  submitButton: "Sign in",
};
```

### 12.3 Error Copy

Error display uses a frontend `errorCodeMap` keyed by stable API error codes.

Example:

```ts
export const errorCodeMap = {
  UNAUTHENTICATED: {
    title: "Your session has expired",
    description: "Sign in again to continue.",
  },
  WORKSPACE_REQUIRED: {
    title: "Workspace is not available",
    description: "Refresh the page or contact an administrator.",
  },
};
```

Rules:

1. `error.code` is the primary mapping key.
2. `details[].code` may be used for field-level mapping.
3. API `message` is fallback only.
4. API `message` must not control branching, navigation or retry behavior.

---

## 13. URL State, Lists and Tables

### 13.1 URL Query State

Allowed URL query keys:

```text
Offset lists:
  page
  pageSize
  q
  tag
  status
  validity
  sort

Cursor lists:
  cursor
  limit
  q
  tag
  status
  validity
  sort only if the Slice explicitly allows it
```

Rules:

1. Temporary UI state must not enter URL.
2. Query params sent to API must follow the API whitelist.
3. Unknown API filter params should return `INVALID_QUERY_PARAMETER`.
4. UI may ignore or normalize unknown URL params.
5. Changing filters resets pagination or cursor state.
6. Search keyword uses `q`.
7. Sort uses `sort`, for example `sort=-createdAt`.

### 13.2 Pagination Defaults

Rules:

1. Default `pageSize` / `limit` should be 20 unless a Slice says otherwise.
2. P0 UI should not default above 50.
3. API max should not exceed 100 unless the Slice explicitly justifies it.
4. Offset lists use `page` and `pageSize`.
5. Cursor lists use `cursor` and `limit`.
6. Run List uses cursor pagination from P0.
7. Ordinary CRUD management lists use offset pagination by default.

### 13.3 List State Components

Required state components:

```text
EmptyState
ErrorState
LoadingSkeleton
```

Every list page must handle:

1. loading state;
2. empty state;
3. error state;
4. loaded state;
5. refetching state where appropriate.

### 13.4 EmptyState

EmptyState content structure:

```text
Title: what is empty
Description: why this matters or what the user can do
Primary action: next action when available
Optional secondary help text
```

Rules:

1. Scenarios empty state guides users to create a Scenario.
2. Test Plans empty state guides users to create a Test Plan.
3. Runs empty state guides users to Run Now after Test Plan exists.
4. Env Groups empty state guides users to create an Env Group.
5. Dependency Files empty state guides users to upload a file.
6. Load Nodes empty state guides users to register a node.
7. P1 import or API Catalog suggestions must not appear in P0 empty states as clickable actions.

### 13.5 ErrorState

ErrorState must explain:

1. what the user was trying to do;
2. why it failed, if known;
3. what the user can do next.

Bad example:

```text
Run failed
```

Good example:

```text
Failed to create run: the selected Public load node is not available.
Choose another Idle node or try again later.
```

Rules:

1. ErrorState must not expose stack traces, SQL errors, credentials, tokens, server paths or raw exception text.
2. ErrorState should show request ID when it helps support or troubleshooting.
3. Field validation errors should appear near fields, not only in a global ErrorState.

### 13.6 Loading and Duplicate Submission

Rules:

1. Lists use LoadingSkeleton or clear loading text.
2. Submit buttons must disable or show pending state during mutation.
3. Destructive actions must remain disabled or guarded while pending.
4. Do not show multiple success toasts for repeated idempotent requests.
5. Run Report running states must show refresh cadence or last refreshed time.
6. Summary generation should show a clear waiting state when terminal Run status is reached but summary is not ready.

### 13.7 Notifications

P0 user feedback should prefer inline status, field-level validation, page-level banners and explicit page states.

Rules:

1. Use inline status for form validation, duplicate submission, pending mutations and recoverable page errors.
2. Use page banners for cross-field or page-level status that should remain visible after navigation within the page.
3. Use toast only for short-lived confirmation or background status where inline placement is not practical.
4. If toast is required, implement a source-owned `Toast` primitive using Radix where needed.
5. Do not introduce `sonner`, `react-toastify` or another third-party notification library in P0.
6. Do not use repeated success toasts for idempotent actions such as repeated Stop requests.

---

## 14. Run Report Polling

Run Report is an observation UI. It must not drive backend state convergence.

Polling rules:

```text
- Poll only when status is initializing / running / stopping.
- Use refetchInterval = 5000.
- Use refetchIntervalInBackground = false.
- Stop polling immediately after terminal status.
- Terminal statuses: finished / failed / aborted.
- If terminal status is reached but summary is not ready, continue short fallback polling.
- Fallback summary polling interval: 5000-10000 ms.
- Fallback summary polling default cap: max 12 attempts or 90 seconds, whichever comes first.
- After fallback summary polling exceeds the cap, show `Summary not yet ready` and provide manual refresh.
- UI polling must never drive backend state transitions.
```

State ownership:

```text
UI only observes state.
Runner callbacks and api-worker own state convergence.
```

Rules:

1. Initializing, Running and Stopping states may show automatic refresh.
2. Finished, Failed and Aborted stop normal polling.
3. Terminal status with missing summary may temporarily poll for summary generation only, capped at max 12 attempts or 90 seconds.
4. Stop is available only for Initializing or Running.
5. Once status is Stopping, the primary action is Refresh, not another Stop action.
6. Frontend must not infer terminal state from timeout alone.
7. Frontend must not release Load Node, mark Run failed or change Run status.
8. Backend state convergence belongs to Runner callback and api-worker.

---

## 15. Page-Specific Rules

### 15.0 Marketing Landing

Marketing Landing page:

1. Uses the ADR-0013 scoped Marketing Landing route, not AuthLayout or AppLayout.
2. Does not call API, does not require Workspace header, and does not require CSRF.
3. Uses local Logo and font assets only.
4. Activates only the ADR-0026/P2-07 public Docs and repository targets; API Guide, Community, Security, and other future items remain disabled unless separately authorized.
5. Replaces static/synthetic live-service and benchmark implications with explicit open-source, self-hosted, illustrative, and non-benchmark labels.
6. User-facing copy is English.

### 15.1 Auth Pages

Login and Register pages:

1. Use AuthLayout.
2. Do not show global navigation.
3. Do not require Workspace header.
4. Do not require CSRF before session exists.
5. Store returned CSRF token in JS memory only.
6. Use generic login error copy for invalid credentials.
7. Do not reveal whether an email exists.
8. Authenticated users visiting `/login` or `/register` are redirected to `/overview`.
9. Login success redirects to `/overview`.
10. Register success redirects to `/overview`.
11. Logout success redirects to `/login`.

### 15.2 Overview

Overview page:

1. Uses AppLayout.
2. Shows P0 summaries only.
3. May show recent Runs, resource status summary and quick entries.
4. Must not show Upcoming Scheduled Jobs in P0.
5. Must not show Monitoring or Grafana cards in P0.

### 15.3 Scenarios

Scenario pages:

1. Use business terminology: Scenario and Visual Scenario.
2. Do not expose Taurus YAML as primary UX.
3. Do not implement cURL import in P0.
4. Do not implement API Catalog import in P0.
5. Debug Run action must show low-risk execution semantics.

### 15.4 Test Plans

Test Plan pages:

1. Use business terminology: Test Plan, Scenario Orchestration, Load Settings, SLA Rules.
2. P0 supports Manual single-node resource selection only.
3. Do not show Auto allocation.
4. Do not show multi-node selection.
5. Do not show Schedule Run.
6. Do not show Generated YAML preview.
7. Show concurrency per node and soft-warning confirmation when required by Slice rules.

### 15.5 Runs and Run Report

Run pages:

1. Run List uses cursor pagination.
2. Run Report focuses on Verdict Summary first.
3. Run Report must distinguish Status, SLA Result and Validity.
4. Artifacts are troubleshooting material, not the primary report conclusion.
5. Validity action must be explicit.
6. Stop action must follow Run state rules.
7. Monitoring entry is not shown in P0.

### 15.6 Assets

Assets pages:

1. Env Groups and Dependency Files are P0 assets.
2. API Catalog is P1 and must not be implemented in P0.
3. Dependency Files use API-mediated upload/download.
4. Web must not receive MinIO credentials.
5. Delete protection errors should explain reference usage when known.

### 15.7 Resources

Load Node pages:

1. P0 supports Public and Private Load Nodes.
2. Public management requires Admin for platform-level operations.
3. Private Load Nodes belong to current Workspace.
4. Credentials are write-only.
5. Admin must not see Private Load Node credential values.
6. Status badges must use stable status values from contracts.

### 15.8 Admin

Admin pages:

1. P0 Admin only implements Setup Status.
2. Setup Status is platform-level read-only with current Workspace checks where needed.
3. Setup Status must not show secret values.
4. User Management is P1.
5. System Settings UI is P1.
6. Workspace Management UI is P1.

---

## 16. Testing Requirements

Frontend tests should cover:

1. route guards;
2. auth redirect behavior;
3. admin 403 behavior;
4. API middleware header injection rules;
5. CSRF token memory storage behavior where testable;
6. Workspace header injection for workspace-aware business APIs;
7. EmptyState / ErrorState / LoadingSkeleton rendering;
8. form validation and duplicate submit prevention;
9. Run Report polling start and stop conditions;
10. no inactive P1/P2 navigation entries; active entries must be backed by their accepted Slice and ADR.

Recommended test placement:

```text
apps/web/src/features/<feature>/*.test.tsx
apps/web/tests/
```

Rules:

1. Component tests should live near components when practical.
2. Cross-route integration tests may live under `apps/web/tests`.
3. Tests must not rely on raw API message text when stable error codes exist.
4. Tests should verify behavior, not implementation details of Tailwind classes, unless class behavior is the contract of a primitive.

---

## 17. Verification and Guards

P0 verification should include:

```text
make verify
```

Web verification should cover:

1. lint;
2. typecheck;
3. component/unit tests where applicable;
4. generated client usage checks where available;
5. no handwritten API request/response types for business APIs;
6. no forbidden visual component system dependencies;
7. no clickable inactive P1/P2 route entries; current accepted Slice routes are explicitly allowlisted.

A future `web:ui-guard` or equivalent script may check:

1. forbidden visual component dependencies are absent;
2. allowed style utility list is not bypassed;
3. `components/ui/*` is covered by lint/typecheck;
4. CSS variable and Tailwind token consistency where practical.

Do not bind this document to an unverified Tailwind CLI check command. Add concrete commands only after the repository implements and validates them.

---

## 18. Review Checklist

Frontend PR Review must check:

### Scope

- [ ] Does not implement P1/P2 UI.
- [ ] Does not add API Catalog, Monitoring, Schedule Run, multi-node execution, Workspace switching, User Management or System Settings UI in P0.
- [ ] Does not add hidden clickable routes for P1/P2.

### Routing and Layout

- [ ] Feature owns its route module.
- [ ] Root router only aggregates route objects.
- [ ] Loader is limited to auth, role, redirect or lightweight metadata.
- [ ] Business data uses TanStack Query.
- [ ] Admin pages reuse AppLayout and AdminSectionLayout.

### UI Stack

- [ ] Does not add Ant Design, MUI, Chakra, Arco, Mantine, DaisyUI or another visual component system.
- [ ] Uses Tailwind + CSS variables as the visual system.
- [ ] Adds source-owned primitives only when required by the active Slice.
- [ ] Does not turn `components/ui/*` into a general-purpose design system.
- [ ] Uses Radix for focus management, keyboard navigation and aria-heavy interactions.

### API, Auth and Security

- [ ] Web uses generated contracts from `@surgepilot/contracts`.
- [ ] Web does not hand-write API request/response types.
- [ ] Web does not call DB, MinIO, Load Node or runner internal endpoints.
- [ ] Workspace header injection follows the middleware rules.
- [ ] CSRF header injection follows the middleware rules.
- [ ] CSRF token is not persisted in browser storage.
- [ ] Frontend permission checks are not treated as final authorization.

### Copy and States

- [ ] User-visible copy comes from copy files.
- [ ] P0 user-facing frontend copy is English only.
- [ ] P0 does not introduce an i18n framework or hidden locale bundles.
- [ ] Error UX maps stable API `code` and `details[].code` to frontend copy.
- [ ] Empty, error and loading states are implemented.
- [ ] ErrorState explains action, reason and next step.
- [ ] API `message` is fallback only.

### Lists and Polling

- [ ] URL query state follows the whitelist.
- [ ] Offset and cursor pagination rules are not mixed.
- [ ] Run Report polling stops on terminal status.
- [ ] Summary fallback polling is capped at max 12 attempts or 90 seconds.
- [ ] UI does not drive backend state convergence.

---

## 19. Done When

This Foundation SDD is satisfied when:

1. `apps/web` follows the feature-based route structure.
2. P0 route guards and layouts follow this document.
3. UI stack uses Tailwind + CSS variables + source-owned minimal primitives.
4. Forbidden visual component systems are absent from new frontend work.
5. API client is generated from contracts and wrapped by a single frontend API client layer.
6. Workspace and CSRF headers are injected according to this document and 04/06.
7. P0 frontend user-facing copy is English only, no i18n framework is introduced, copy is stored in copy files, and error UX maps stable API codes.
8. EmptyState, ErrorState and LoadingSkeleton are used consistently.
9. Run Report polling follows status-based rules and does not drive state convergence.
10. Review checklist is used in frontend Slice reviews.
