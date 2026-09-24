# ADR-0027: Product Version and Artifact Identity

- Status: Accepted
- Scope: Repository-wide product-version authority, runtime metadata, and release-artifact identity
- Related issue: `#34 Propagate the tagged release version into SurgePilot OpenAPI metadata`

## Context

SurgePilot currently repeats placeholder `0.1.0` values across Python and private npm manifests,
FastAPI metadata, Runner output, generated OpenAPI, and tests. The tagged release workflow already
supplies release metadata to image builds, but the API does not consume that metadata at runtime.
Consequently, a release tagged `vX.Y.Z` can still expose unrelated OpenAPI metadata and bootstrap
that unrelated value into the Default Workspace API Catalog.

The repository also has several distinct identities that must not be collapsed into one string:
the SurgePilot product version, a release or validation artifact version, a registry tag, a source
revision, Runtime component versions, and deterministic Runtime manifest hashes. A single policy is
needed so later changes do not reintroduce placeholders or use Git availability as a runtime
dependency.

## Options Considered

### Option A: One checked-in product version with bounded lockstep consumers

Accepted. A repository-root `VERSION` file owns the canonical product version. Only components
that expose product identity or provide the documented source/local fallback copy it. Automated
verification detects drift, while release workflows keep artifact identity separate.

### Option B: Derive the product version from Git at runtime

Rejected. Published images, installed Python packages, and uploaded Runner bundles must work
without a Git checkout. Dirty trees and shallow clones would also make the fallback ambiguous.

### Option C: Give API, Runner, Web, contracts, and documentation independent versions

Rejected. SurgePilot publishes one first-party product and has no current requirement for
independently released components. Independent version policy and compatibility negotiation would
add unsupported lifecycle work.

### Option D: Synchronize every package manifest with the product version

Rejected. The root npm workspace, Web, contracts, and documentation packages are private and do
not publish or expose package versions. The root Python project is a virtual workspace rather than
a product package. Keeping meaningless version fields would create release churn without adding
identity.

## Decision

1. The repository-root `VERSION` file is the authority for the SurgePilot product version. It is
   UTF-8, contains exactly one canonical `X.Y.Z` line followed by one newline, has no leading `v`,
   whitespace, prerelease, or build suffix, and must not be `0.0.0`. Numeric components have no
   leading zero unless the component is exactly `0`.
2. The API and Runner Python package metadata remain equal to `VERSION`. They provide the
   deterministic source/local fallback for those installed applications. The private npm
   workspaces and root virtual Python workspace declare no product version.
3. Product-version consumers are the API/OpenAPI `info.version`, curated and public generated
   OpenAPI, the Public API AI skill snapshot, active system-owned Catalog `documentVersion` and stored curated OpenAPI `info.version`, the
   generated Runner bundle version, Runner CLI output, detected `runnerVersion`, and Web display
   derived from Catalog metadata.
4. The API resolves its product version from `SURGEPILOT_PRODUCT_VERSION` when the variable is
   non-empty. It removes at most one leading `v`, validates the canonical result, and fails closed
   on an explicitly malformed value. When the variable is missing or empty, it resolves and
   validates installed `surgepilot-api` package metadata. Missing or malformed fallback metadata
   is a startup error. Runtime Git probing is forbidden.
5. The API passes the same resolved product version to remote Runner source bundles by generating
   `surgepilot_runner/VERSION` in memory from `RunnerBundle.files()`. This generated file is not
   committed. Runner `version` reads and validates the bundle file first, then falls back to
   installed `surgepilot-runner` package metadata only when the file is absent. Invalid present
   content and unavailable or invalid fallback metadata fail closed. Runner never imports API
   internals.
6. Product identity and release-artifact identity remain distinct:

   | Identity | Source/local | Development validation | Formal release |
   | --- | --- | --- | --- |
   | Product metadata | `X.Y.Z` | `X.Y.Z` | `X.Y.Z` |
   | OCI image version | `dev` | `v0.0.0` | `vX.Y.Z` |
   | Registry tag | local | `validation-<full-source-identifier>` | `vX.Y.Z` |
   | Release manifest / Runtime artifact version | none or development hash semantics | `v0.0.0` | `vX.Y.Z` |
   | Source revision | local/unknown | full source identifier | release commit identifier |

   `v0.0.0` never enters API, OpenAPI, Catalog, skill, or Runner product metadata. Validation
   changes the existing OCI version label from `validation-<source-identifier>` to the reserved
   validation artifact version `v0.0.0`; candidate identity remains in the registry tag and OCI
   revision label. A formal release candidate instead uses its target `vX.Y.Z` artifact version
   under run-specific `staging-<run-id>-<attempt>[-arch]` image tags. Only after all required
   smoke jobs pass do semantic image tags point at those recorded digests.
7. A formal release tag must equal `v` plus the root product version. Ordinary feature, bug,
   documentation, test, and refactoring work does not change `VERSION` unless the approved task
   explicitly includes a product-version or release change. Historical tags and persisted
   `runnerVersion` observations are not rewritten or migrated; a later node initialization records
   the newly installed Runner version. The formal release workflow builds its pre-tag candidate with
   that exact target artifact version; the separate development-validation workflow continues to use
   `v0.0.0` artifacts.
8. FastAPI/Pydantic remains the OpenAPI source. Generated internal/public OpenAPI, generated Web
   clients, and the AI skill snapshot are regenerated through `make generate-contracts` and are
   never stamped or hand-edited during Docker builds.
9. Repository verification checks the canonical root value, API/Runner Python metadata, absence of
   pseudo product versions in private workspace manifests, generated OpenAPI and skill freshness,
   resolver behavior, Runner bundle behavior, formal tag alignment, and release workflow wiring.
   Native release validation additionally checks built image labels and the running API, Catalog,
   Runner, and skill snapshot against the expected identities.

The following remain outside product-version governance: third-party dependencies, Taurus/JMeter
versions, Runtime component versions, Runtime `manifestHash`, Git SHA, validation registry tags,
API URL `/v1`, database migration numbers, `bundleVersion`, and historical release records.

## Consequences

1. A tagged `vX.Y.Z` API image exposes `X.Y.Z` consistently through runtime and generated OpenAPI,
   active system-owned Catalog metadata and stored curated OpenAPI, and the installed Runner bundle.
2. Source and local operation remain deterministic without Git and fail clearly when installed
   metadata is unavailable or malformed.
3. Validation can retain its reserved release artifact `v0.0.0` without contaminating product
   metadata or requiring Docker-time contract generation.
4. Releases update one root authority, two meaningful Python package metadata fields, and generated
   artifacts; private workspace manifests do not create mechanical version churn.
5. This decision adds no version service, release bot, independent component lifecycle,
   compatibility registry, database migration, or automatic upgrade mechanism. The later P2-04
   lifecycle amendment introduces the server-only `system_key` migration; it does not revise this
   decision's original implementation history.

## Related ADRs

- `docs/sdd/adr/ADR-0002-runner-independent-app.md`
- `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`

## References

- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/slices/P0-03-load-nodes.md`
- `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`
- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `AGENTS.md`
