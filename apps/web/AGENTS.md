# Web Agent Notes

- Follow root `AGENTS.md` and `docs/sdd/08-frontend-routing-and-ui-rules.md` when UI work starts.
- This file is subordinate to `/AGENTS.md`; when conflicts occur, follow root AGENTS and the referenced SDD.
- Follow root verification gates and `docs/sdd/09-testing-and-acceptance-strategy.md` for test expectations.
- Web calls API only through generated contracts from `@surgepilot/contracts`.
- Import generated client/types only through the `@surgepilot/contracts` workspace dependency; do not import `packages/contracts/generated/...` by relative path.
- UI stack is Tailwind CSS + CSS variables + source-owned minimal primitives, per `docs/sdd/08-frontend-routing-and-ui-rules.md`.
- Do not add Ant Design or another third-party visual component system unless `docs/sdd/08-frontend-routing-and-ui-rules.md` is explicitly updated.
- Do not access PostgreSQL, MinIO, Load Nodes, or runner endpoints directly.
- Do not hand-write API request or response types.
- Add clickable P1 routes only when a named accepted P1 Slice SDD is active, and keep route/module changes inside that Slice.
- Do not add P2 navigation or product capabilities unless a separate accepted scope source activates them.

- ADR-0013 authorizes the static public `/` Marketing Landing and Logo migration. ADR-0026/P2-07 narrowly adds the exact public Docs and repository targets plus the explicitly labelled synthetic dashboard, Recent Test Runs, and Distributed load mesh UI demonstrations; keep the route in `features/marketing`, lazy-load it, use local assets, preserve Log in/Sign up and auth redirects, and do not add Help/Community/API Guide or other product capabilities.
- ADR-0016/P2-04 separately authorizes authenticated `/help` with the exact Help AI Agents tab/copy boundary and the session skill-source download action. Public Landing Docs/repository links are authorized only by ADR-0026/P2-07; P2-04 does not activate SDK, MCP, marketplace, installer, built-in agent runtime, or AI generation/tuning/analysis.
