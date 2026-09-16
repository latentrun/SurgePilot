# AI Authorship and Evidence

SurgePilot is an inspectable experiment in governed agentic software engineering. The strong
public claim is deliberately narrower than “no human participated”:

> The original public baseline was authored end-to-end by AI agents under human direction.

## Responsibility boundary

| Participant | Responsibilities for the original public baseline |
| --- | --- |
| Human | product intent; requirements discussion; product use; usage feedback; result acceptance |
| AI agents | product and engineering-process design; PRD, SDD, ADR, and Slice authorship; architecture and contracts; implementation and tests; quality-gate design and enforcement; verification-failure resolution; deployment and release assets |

The human did not manually produce the original baseline's first-party engineering artifacts. The
human did participate by setting intent, discussing requirements, using the system, providing
feedback, and deciding whether results were acceptable.

## Baseline status

**Baseline tag: not selected.** This private-stage repository does not yet identify a released
baseline. Public activation is blocked until the owner selects one immutable semantic-
version tag, publishes the matching installable Release, and records both here.

Once recorded, the 100% AI-authored statement applies only to that immutable tag and its preserved
baseline record. It does not automatically apply to later contributions.

| Record | Value |
| --- | --- |
| Immutable baseline tag | Pending public-readiness review |
| Matching GitHub Release | Pending public-readiness review |
| Verification record | Pending final candidate verification |

## Repository evidence map

Private agent conversations are not required to evaluate the claim. The primary evidence is the
reviewable and executable chain in this repository:

1. [Agent execution contract](AGENTS.md) — context routing, scope control, workflow, and gates.
2. [Product requirements](docs/prd/PRD.md) — the product source.
3. [System design entry](docs/sdd/README.md) — foundations, ADRs, and accepted Slice SDDs.
4. [Architecture overview](docs/sdd/01-architecture-overview.md) — service and trust boundaries.
5. [Public OpenAPI contract](packages/contracts/openapi/public-api.openapi.json) — generated public
   interface evidence.
6. [`apps/`](apps) and [`packages/`](packages) — implementation and generated consumers.
7. [Testing strategy](docs/sdd/09-testing-and-acceptance-strategy.md) and [`Makefile`](Makefile) —
   executable quality gates, including `make verify`.
8. [Release workflows](.github/workflows) and [`infra/release/`](infra/release) — deployment and release assets.

Repository materials become evidence after public-readiness review has checked them for
privacy, credentials, author metadata, and license issues. Passing tests demonstrates current
behavior; it does not by itself prove historical authorship.

## Future contributions

Future contributions may be human- or AI-authored. Contributors do not need to disclose or prove
which tools they used, and no model, prompt, or provenance attestation is required. Contributions
are reviewed on scope, technical merit, security, tests, and repository policy. See
[CONTRIBUTING.md](CONTRIBUTING.md).

Screenshots or redacted conversation excerpts may be added later as optional context. They are not
part of the minimum evidence chain and must pass a separate privacy review.
