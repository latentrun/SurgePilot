# Web Agent Instructions

Scope: `apps/web/**`.

Inherits `/AGENTS.md`. This file adds Web-specific constraints and review rules. Consult
`docs/sdd/08-frontend-routing-and-ui-rules.md` for route, layout, or interaction changes.

- Call API through the generated `@surgepilot/contracts` workspace package.
- Import generated client/types through the package entry point; never use relative imports into
  `packages/contracts/generated` and never hand-write API DTOs.
- Web does not access PostgreSQL, MinIO, Load Nodes, or internal Runner endpoints directly.
- Preserve the approved Tailwind CSS, CSS-variable, and source-owned primitive stack. A new visual
  component system requires an accepted design change.
- A user-visible route, navigation item, or capability requires explicit active design authority.

## Code Review Rules

- Flag handwritten or duplicated API request/response shapes.
- Flag clickable routes or actions whose capability is not active.
- Flag authorization or Workspace enforcement implemented only in the browser.
- Flag direct infrastructure access or generated-client imports that bypass the workspace package.
