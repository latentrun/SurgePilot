# Contributing to SurgePilot

Thank you for improving SurgePilot. Contributions may be human- or AI-authored. No model, prompt,
transcript, or provenance attestation is required; review is based on the submitted change.

## Before opening a change

1. Read [`AGENTS.md`](AGENTS.md), the [SDD entry](docs/sdd/README.md), and the
   [scope gate](docs/sdd/00-product-scope-and-priority.md).
2. Confirm that an accepted ADR and Slice SDD authorize the capability. Open a proposal first when
   the scope is not active.
3. Create a focused branch from `main`. Do not mix unrelated cleanup with the contribution.
4. For executable behavior, add a failing test before implementation. Update contracts before
   their consumers and do not hand-edit generated contract output.

Small documentation corrections and clearly scoped bug reports are welcome. Large feature pull
requests without an accepted scope source may be closed even when the implementation works.

## Development and verification

Set up the repository with:

```bash
make setup
```

Run the smallest relevant tests while developing. Before requesting review, run:

```bash
make generate-contracts
make contracts-stale-check
make verify
```

Run `make verify-e2e` only when the change requires its Docker and SSH integration coverage and
the necessary environment is available. Document any gate you could not run and why.

## Pull requests

- Target the `main` branch unless a maintainer requests otherwise.
- Explain the problem, authorized scope, solution, security impact, and verification evidence.
- Keep commits reviewable and never include credentials, private endpoints, personal data, or
  unlicensed assets.
- Update an ADR or SDD only when implementation facts or accepted decisions changed.
- Accept technical review based on repository contracts, regardless of whether the contribution
  was written by a person, an AI agent, or both.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md) and license your
contribution under the repository's [MIT License](LICENSE).
