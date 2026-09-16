# P2 Slice writing brief / thin index

## Purpose / Usage

This document is only a P2 Slice writing brief and scope index. It does not replace the PRD, `docs/sdd/00-product-scope-and-priority.md`, `AGENTS.md`, ADRs, or any real Slice SDD.

P2 capabilities remain inactive until a named accepted P2 Slice SDD and any required governance decision activate implementation. This index does not authorize implementation by itself. `P2-00-api-catalog-scalar.md` is active through `ADR-0010`; `P2-01-openapi-step-generation.md` is active through `ADR-0011`; `P2-02-public-api-substrate.md` is active through `ADR-0012`; `P2-03-env-group-secret.md` is active through `ADR-0014`; `P2-04-help-ai-agents-system-openapi-bootstrap.md` is active through `ADR-0016`; `P2-05-cross-platform-distribution.md` is active through `ADR-0017`, its source-preview amendment `ADR-0019`, and its user-local platform Release installer amendment `ADR-0024`; `P2-06-lan-first-deployment-usability.md` is active through `ADR-0018`, its new-release Runtime default amendment `ADR-0020`, its release `up` configuration confirmation amendment `ADR-0021`, and its separate installation amendment `ADR-0024` as release-path amendments to P2-05; `P2-07-public-launch-github-pages-seo.md` is active through `ADR-0026`. `ADR-0013` remains limited to the self-hosted static Marketing Landing / Logo only, while ADR-0026 separately governs the public Pages marketing site.

## Authoritative References

Use only these references for P2 Slice drafting decisions:

- P2 scope: `docs/sdd/00-product-scope-and-priority.md` §7.
- Frontend planned-route boundary: `docs/sdd/08-frontend-routing-and-ui-rules.md` §5.4.
- API contracts: `docs/sdd/04-api-contract-guidelines.md`.
- Security and Workspace boundary: `docs/sdd/06-security-permission-workspace.md`.
- Storage boundary: `docs/sdd/07-storage-artifacts-minio.md`.
- Agent constraints for architecture, contracts, language, and verification gates: `AGENTS.md`.

## P2 Slice Index

The following files are the current P2 Slice index. Real active Slice SDDs are authoritative only for their own scoped capability.

1. `docs/sdd/slices/P2-00-api-catalog-scalar.md` -- active P2 Slice SDD for API Catalog documentation asset management using Scalar API Reference as the detail-page renderer, authorized by `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`. It does not authorize P0/P1 implementation or any API Catalog → Scenario/Test Plan generation chain.
2. `docs/sdd/slices/P2-01-openapi-step-generation.md` -- active P2 Slice SDD for Scenario editor OpenAPI Step draft generation from authorized API Catalog spec assets, authorized by `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`. It is not an API Catalog detail-page action and does not authorize Scenario/Test Plan generation chains.
3. `docs/sdd/slices/P2-02-public-api-substrate.md` -- active P2 Slice SDD for programmatic public API substrate, Account self-service API keys, PAT Bearer public business API, public OpenAPI export, structured config writes, Run lifecycle access, bounded Dependency File list/upload/delete, and one governed repo-maintained Public API AI skill source package, authorized by `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`. The Dependency File extension reuses existing storage/validation/Workspace/reference-protection rules and does not authorize public preview/download. It does not authorize public key-management routes, admin-managed keys, Help/download UI outside P2-04, release distribution, SDK, MCP server, skills runtime, or any API Catalog → Scenario/Test Plan generation chain.
4. `docs/sdd/slices/P2-03-env-group-secret.md` -- active P2 Slice SDD for Env Group `plain | secret` typed variables, session masked secret read models, session-only secret writes, plain-only public DTOs, required one-time string-map-to-plain migration, and public API secret exclusion, authorized by `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`. It does not authorize Snapshot encryption, key rotation, reveal API, or external Secret Manager integration.
5. `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md` -- active P2 Slice SDD for authenticated Help AI Agents guidance, session-authenticated request-built Public API AI skill source download, shared runtime/script OpenAPI export, and best-effort first-Admin import of SurgePilot's own curated Web/business OpenAPI into Default Workspace API Catalog, authorized by `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`. It does not authorize user/external automatic ingestion, release distribution, SDK, MCP, marketplace, installer, agent runtime, retries/workers, AI generation/tuning/analysis, or API Catalog to Scenario/Test Plan generation.
6. `docs/sdd/slices/P2-05-cross-platform-distribution.md` -- active P2 Slice SDD for one complete tagged-release mode using GHCR multi-architecture SurgePilot application images, a bounded GitHub Release bundle, the version-pinned user-local installer and checksum authorized by ADR-0024, native-built Linux amd64/arm64 Runtime assets, release Compose plus `surgepilot up`, source Compose plus complete `make start-full-stack` and control-plane-only `make start-preview` entries, and Monitoring, authorized by `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`, amended for source preview by `ADR-0019`, and amended for LAN-first release startup by P2-06/ADR-0018 plus its new-release Runtime default through ADR-0020, release configuration confirmation through ADR-0021, and separate installation entry through ADR-0024. It does not authorize Kubernetes, package-manager/system installers, Docker Hub mirroring, all-in-one images, native macOS Load Nodes/Runtime, automatic upgrades, Runtime UI/catalog, signing/SBOM publication, or standalone Public API AI skill release.
7. `docs/sdd/slices/P2-06-lan-first-deployment-usability.md` -- active P2 Slice SDD for release-only interactive LAN first-run bootstrap with an explicit warned loopback-origin evaluation exception, persisted node-facing URL/port consistency, Demo-off release default, strict cookie transport configuration, default authenticated InfluxDB publication, non-interactive CI `.env` fixtures, and the separate user-local installation entry authorized by ADR-0024. It is authorized by `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md` and amended by `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`, `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`, and `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`. New tagged-release deployments persist `amd64,arm64` without an architecture prompt. Every valid `up` displays the bounded non-secret configuration; interactive default-Yes is read-only, explicit No/re-entry/Yes may change only four standard-LAN network fields, non-interactive startup never rewrites, and advanced HTTPS remains manual-edit-only. All four Runtime values remain available for advanced use, and source startup remains native-only. The loopback exception does not change all-interface published-port binding. It does not add network discovery, Web/API configuration surfaces, package-manager/system installers, or public workflow dispatch capability.
8. `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md` -- active P2 Slice SDD for the coordinated `latentrun/SurgePilot` public launch, one statically generated VitePress Pages marketing/docs site, original AI-authored baseline evidence, explicitly labelled synthetic Landing dashboard/Run/Distributed mesh UI demonstrations, publication SEO and international alternates, self-hosted Web `noindex`, demo/social assets, and public-readiness gates, authorized by `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`. It does not authorize hosted SurgePilot, pricing, billing, leads, a blog/CMS, programmatic SEO, custom-domain launch, automatic translation, product localization, fabricated benchmark/adoption/status/Star claims, or changes to product/release execution contracts.

## Cross-cutting Constraints

Contract-first rules, Workspace isolation, permission checks, Runner/Web/API boundaries, language rules, and verification gates remain governed by the authoritative references above. This README intentionally does not restate those rules.

P2 placeholder or index documents must not create clickable P2 UI, callable P2 API behavior, or P2 execution dependencies. Implementation requires a real accepted P2 Slice SDD plus any required governance activation.

P2 API Catalog remains documentation asset management only. It must not create, update, import, or generate Scenario/Test Plan behavior.

P2 OpenAPI Step Generation is a Scenario editor Step draft helper only. It must not create Scenario/Test Plan records, must not expose generation actions from API Catalog detail pages, and must not persist API Catalog operation resources.

P2-04's system OpenAPI bootstrap is a one-time best-effort system-owned Catalog asset exception. It does not authorize automatic ingestion of user, external, remote, repository, or arbitrary OpenAPI documents.

P2-05's platform release artifacts do not change P2-02/P2-04 Public API AI skill distribution boundaries. The platform bundle may publish application images and Linux Runtime assets only; the skill remains repository source plus the authenticated request-built download.

ADR-0019's source preview changes only Make/Compose startup orchestration and Runtime build output.
It adds no API, OpenAPI, Workspace, permission, database, Web, Runner, skill, or release capability.

ADR-0020 changes only the missing-`.env` tagged-release Runtime default and removes the first-run
architecture prompt. It preserves existing release `.env` values and every other ADR-0018 LAN,
Demo, cookie, InfluxDB, published-port, non-interactive, source-startup, and capability boundary.

ADR-0021 changes only tagged-release `up` configuration review and explicit interactive
standard-LAN re-entry. Automatic and non-interactive rewriting remains forbidden; advanced HTTPS
requires manual editing, all non-network values are preserved, and source startup is unchanged.

ADR-0026 adds only the public repository/Pages/SEO/authorship-evidence and self-hosted indexing
boundary defined by P2-07. It consumes P2-05/P2-06 release artifacts without changing release
startup, Runtime, Compose, installer, or integrity contracts.

## Revision Protocol

This README must not independently enlarge P2 scope. Any new or changed P2 capability must first update the PRD or add a confirmed ADR, then synchronize `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `AGENTS.md`, and this index where applicable.

Before submitting changes to this README, verify that it still avoids implementation design duplication and does not activate P2 capabilities by itself.

## Verification Backfill

The reconstructed P2-07 verification is recorded in
`docs/sdd/slices/P2-07-public-launch-github-pages-seo.md` §14. The focused P2-07 commands are
`make docs-site` and `make docs-site-build` for the VitePress package under `docs/site`, and
`make verify-p2-07-public-launch` for the built/rendered site verification together with the
`tests/contract/test_p2_07_public_launch.py` and `tests/contract/test_user_docs_locales.py`
contracts. The private build-and-verify workflow is `.github/workflows/pages-build.yml`, which
holds `contents: read` only and no Pages deployment authority. Rendered browser, asset-budget, and
anonymous repository/Release/Pages smoke steps remain environment- or launch-gated and are not
part of default `make verify`; the reconstruction publishes as `latentrun/SurgePilot` on `main`
with `ghcr.io/latentrun/*` images.
