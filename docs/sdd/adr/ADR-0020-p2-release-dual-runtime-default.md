# ADR-0020: P2 Release Dual-Architecture Runtime Default

- Status: Accepted
- Scope: P2-06 tagged-release bootstrap default only
- Partial supersession: ADR-0017 Decision 8 and ADR-0018 statements selecting `auto` and asking for
  Runtime architectures
- Active Slice: `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Related ADRs: `ADR-0017-p2-cross-platform-distribution`,
  `ADR-0018-p2-lan-first-release-bootstrap`,
  `ADR-0021-p2-release-up-configuration-confirmation`

## Context

ADR-0018 made tagged-release startup LAN-first and selected the Docker daemon architecture through
the persisted `SURGEPILOT_RUNTIME_ARCHITECTURES=auto` default. It also asked first-run operators to
choose the Runtime architecture set. That keeps the initial download small, but architecture
selection is infrastructure detail and the daemon architecture does not predict the architecture
of a later external Load Node.

A new tagged-release deployment should be ready for both supported external Load Node
architectures without another bootstrap decision. The change must remain release-only: source
startup builds a native development Runtime with a source-derived version and must not download or
combine a second semantic-release Runtime.

## Decision

1. New tagged-release deployments default to
   `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64`.
2. Interactive first-run `./surgepilot up` does not ask for Runtime architectures.
3. Existing `.env` Runtime, Demo, cookie, credential, secret, and other non-network values remain
   authoritative and are never rewritten by this ADR. ADR-0021 separately permits only an explicit
   interactive update of four allowlisted standard-LAN network fields.
4. `auto`, `amd64`, `arm64`, and `amd64,arm64` remain accepted advanced values.
5. Source startup remains native-only and root `.env.example` remains `auto`.
6. Both selected prebuilt Runtime sets validate before release Compose startup.

The selected Runtime archives, checksum sidecars, release manifests, release version, platform,
architecture, components, plugins, and manifest hashes continue to use the existing P2-05/P2-06
integrity contract. Missing or invalid assets for either selected architecture fail before Compose
startup side effects. No Runtime is compiled on the tagged-release deployment host.

## Rejected Alternatives

### Make source startup dual-architecture

Rejected. Source `make start-full-stack` and `make release-runtime` remain native-only. Building a
second architecture would require cross-compilation or emulation and would violate the fast,
source-version-consistent development boundary.

### Build the second Runtime through QEMU

Rejected. QEMU adds host tooling, performance, and reproducibility costs. Tagged releases already
provide native-built, checksummed Runtime assets for both supported architectures.

### Mix a source Runtime with a semantic-release Runtime

Rejected. Combining a `dev-<manifestHash>` Runtime with a released semantic version would break the
single-version Runtime integrity and compatibility contract.

### Download the other architecture lazily

Rejected. Background or Load-Node-triggered acquisition would defer failure until initialization,
add mutable lifecycle behavior, and require retry, update, or Runtime-management capability outside
P2-06.

## ADR-0017 and ADR-0018 Supersession Boundary

This ADR partially supersedes ADR-0017 Decision 8 only where it selects `auto` as the normal
missing-`.env` tagged-release default or carries forward a first-run Runtime architecture prompt.

This ADR partially supersedes only ADR-0018 statements that:

1. select `auto` as the new tagged-release default; or
2. require interactive first-run `./surgepilot up` to ask for Runtime architectures.

ADR-0018 remains Accepted and authoritative for explicit LAN host and port confirmation, the
Demo-off default, strict cookie transport, authenticated InfluxDB publication, the warned
loopback-origin exception, all-interface published-port binding, non-interactive complete `.env`
fixtures, and preservation of existing deployment state. Existing persisted `auto` or explicit
single/dual architecture values remain valid and are never migrated automatically.

ADR-0021 partially supersedes only this ADR's unqualified existing-`.env` no-rewrite wording. It
does not change the dual-Runtime default: current configuration confirmation is read-only by
default, and an interactive No/re-enter/Yes sequence may update only four standard-LAN network
fields. Runtime architecture values remain untouched. Non-interactive rewriting remains forbidden,
advanced HTTPS remains manual-edit-only, and source startup remains native-only.

## Consequences

1. New tagged-release deployments acquire and validate both official Linux Runtime sets before
   release Compose startup, so later amd64 and arm64 external Load Nodes are supported by default.
2. First-run interaction is simpler because the operator confirms only the host and published
   ports before the configuration is persisted.
3. Cold release startup downloads and stores one additional Runtime archive, checksum sidecar, and
   manifest. Failure of either default asset fails startup even if the immediate host needs only
   one architecture.
4. Advanced or automated deployments may still deliberately persist any accepted Runtime value.
5. Existing release Runtime selection and source-checkout behavior do not change; ADR-0021's
   explicit interactive four-field network update is the only existing-`.env` exception.
6. No P2-02, API, database, migration, Web, OpenAPI, Workspace, permission, Runner protocol, or
   Runtime-format capability is added.

## References

- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`
- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `AGENTS.md`

## Verification Backfill

`tests/test_release_preflight.py` verifies the new-release `amd64,arm64` default and the
`auto`/`amd64`/`arm64`/`amd64,arm64` boundaries, `tests/test_release_wrapper.py` verifies that a
new release never prompts for Runtime architectures and validates both Runtime sets before Compose
startup, and `tests/test_bootstrap_deployment_env.py` verifies the persisted Runtime value and
existing-`.env` preservation. `tests/test_p2_05_release_stack_verifier.py` covers the dual-default
release-stack contract. The full P2-06 verification backfill is recorded in
`docs/sdd/slices/P2-06-lan-first-deployment-usability.md` §21.
