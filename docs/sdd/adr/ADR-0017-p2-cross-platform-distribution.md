# ADR-0017: P2 Cross-platform Distribution and Full-stack Release Bootstrap

- Status: Accepted
- Scope: P2-05 public cross-platform distribution, tagged release bootstrap, multi-architecture application images, and Linux Runtime release assets
- Active Slice: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- Release startup amendment: Decisions 7 and 8 are partially superseded by `ADR-0018` only as
  specified in `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`.
- Release Runtime default amendment: Decision 8 is partially superseded by `ADR-0020` only for the
  missing-`.env` tagged-release default and first-run Runtime architecture prompt, as specified in
  `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`.
- Release configuration confirmation amendment: Existing-`.env` no-rewrite wording is partially
  superseded only by `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md` for an
  explicit interactive standard-LAN four-field update after No, normalized review, and Yes.
- Source startup amendment: source-only preview exclusion statements are partially superseded by
  `ADR-0019`; the complete `make start-full-stack` and single tagged-release mode remain unchanged.
- Related ADRs: `ADR-0007-p0-runtime-bootstrap-packaging`, `ADR-0012-p2-public-api-substrate`, `ADR-0016-p2-help-ai-agents-system-openapi-bootstrap`

## Context

SurgePilot's source-checkout startup is suitable for contributors, but the future open-source project also needs one complete low-friction release path for users who only want to evaluate or deploy the platform. Most expected local evaluators use Apple Silicon macOS, while real Load Nodes and the Load Node Runtime remain Linux-only.

The release path must show the complete platform without creating preview/full release modes or requiring host Python, Node.js, Java, Taurus, or JMeter. ADR-0019 separately authorizes a source-only control-plane preview that is not a release mode or execution-readiness claim. Both paths preserve the existing api-worker-to-Load-Node Runtime delivery boundary and avoid turning Runtime packaging into a product-management capability.

The accepted design is fully specified by `P2-05-cross-platform-distribution.md`. This ADR activates that Slice and records only the remaining governance selections.

## Options Considered

### Option A: GHCR application images plus GitHub Release bundle and Runtime assets

Accepted.

This option keeps application images in one OCI registry, publishes architecture-specific Linux Runtime archives as ordinary release assets, and gives release users one `./surgepilot up` entry while retaining `make start-full-stack` for source checkouts.

### Option B: Keep source checkout and local image builds as the only public path

Rejected.

This would continue to require repository and build-tool knowledge from evaluation users and would not provide a stable tagged-release integrity boundary.

### Option C: Publish an all-in-one image, native macOS Runtime, or multiple registry/package-manager variants

Rejected.

These alternatives increase lifecycle, compatibility, and support cost without improving the required complete Docker-based user experience. They remain outside P2-05.

## Decision

1. Activate `P2-05 Cross-platform Distribution and Full-stack Release Bootstrap` exactly within `docs/sdd/slices/P2-05-cross-platform-distribution.md`.
2. Publish SurgePilot-owned application images under:
   - `ghcr.io/latentrun/surgepilot-api`
   - `ghcr.io/latentrun/surgepilot-web`
   - `ghcr.io/latentrun/surgepilot-demo-node`
3. Use an exact `vX.Y.Z` Git tag as the only public release trigger. The tagged workflow is create-only: any pre-existing semantic GHCR tag or GitHub Release for that version fails publication and requires a new version.
4. The publication job uses only `contents: write` and `packages: write`; it does not request `id-token: write` or unrelated repository permissions. Pull-request and ordinary branch workflows remain read-only and never publish.
5. Build release-grade `linux-amd64` and `linux-arm64` Runtime assets on native Linux architecture runners. GitHub-hosted native Linux runners are the selected source. If the required native arm64 runner is unavailable, the release is blocked; QEMU or cross-compilation is not an acceptance substitute. A future self-hosted runner requires an explicit governance amendment.
6. Keep source and release startup contracts separate:
   - source checkout: source Compose plus `make start-full-stack`;
   - tagged release bundle: release Compose plus `./surgepilot up`.
     Release Compose pulls immutable image digests and contains no application build context or source-build fallback.
7. The original P2-05 complete default topology used Compose-internal Demo Load Node API and
   InfluxDB origins. ADR-0018 supersedes that release default with explicit persisted origins, Demo
   disabled by default, normal LAN/external-node readiness, and a warned explicit loopback-origin
   evaluation exception. That exception does not change the release Compose published-port bind;
   source Compose internal defaults are unchanged.
8. New missing-`.env` tagged-release deployments default to
   `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64` under ADR-0020 and do not ask for Runtime
   architectures. Existing `.env` values remain authoritative, and `auto`, `amd64`, `arm64`, and
   `amd64,arm64` remain accepted advanced values. When explicitly persisted, `auto` retains the
   ADR-0018 meaning of the Docker daemon architecture even when Demo is disabled. These values do
   not create a Runtime catalog.
9. The platform release bundle, application images, and Runtime archives do not publish the Public API AI skill as a standalone release artifact. The P2-02/P2-04 skill boundaries remain unchanged.
10. ADR-0019 adds source-only `make start-preview`/`make stop-preview` entries and Runtime build
    observability without changing `make start-full-stack`, release Compose, `./surgepilot`, or any
    released artifact.
11. Under ADR-0021 every valid release `up` displays its bounded non-secret effective
    configuration before Runtime fetch. Interactive startup uses default-Yes `[Y/n]`; accepting the
    current configuration is read-only, while No may enter a standard-LAN loop that updates only
    the four allowlisted network fields after normalized review and Yes. Non-interactive startup
    never prompts or rewrites, advanced HTTPS requires manual `.env` editing, and source startup is
    excluded.
12. Under ADR-0024 every semantic platform Release also publishes one exact-version POSIX
    `install.sh` and one SHA-256 bundle sidecar. The installer publishes the existing bounded
    bundle below the user's home directory and creates a user-owned launcher; startup remains the
    separate interactive `surgepilot up` command.

## Consequences

1. P2-05 becomes an active implementation scope, but this activation PR does not implement the wrapper, release Compose, image publication, Runtime download, or release workflow.
2. Until P2-05 implementation lands, the repository's existing `make start-full-stack` behavior remains the available source-checkout startup implementation. Implementation must remove new reliance on automatic external-node URL discovery and converge to the explicit final-URL contract above.
3. Public release publication depends on GitHub Release, GHCR, and native GitHub-hosted Linux arm64 runner availability.
4. The full default stack has a larger download and Docker resource footprint than a partial preview stack; P2-05 deliberately accepts that cost to preserve one complete user mode.
5. Kubernetes, package-manager or system installers, Docker Hub mirroring, native macOS Load
   Nodes/Runtime, all-in-one images, automatic upgrades, Runtime UI/catalog, signing, SBOM
   publication, and standalone AI skill release remain inactive. ADR-0024 authorizes only its
   bounded user-local platform Release installer.
6. `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/slices/P2-README.md`, and `AGENTS.md` are synchronized in the activation PR.

## References

- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0007-p0-runtime-bootstrap-packaging.md`
- `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`
- `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`
- `docs/sdd/p0-runtime-bootstrap-plan.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `AGENTS.md`
