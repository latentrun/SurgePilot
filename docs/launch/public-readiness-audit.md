# Public Readiness Audit

- Overall status: RELEASE CANDIDATE APPROVED
- Effect: the owner approved the reviewed public metadata, fixture allowlist, author exposure, and
  asset provenance for `v1.0.0`; semantic publication remains gated on exact-candidate validation

Raw matches are intentionally not copied into this file. Local scan output may contain credentials,
personal information, internal endpoints, or author metadata; it remains in an access-controlled
temporary location and is deleted after owner review.

This is a bounded pattern and provenance audit, not proof that no secret exists. Gitleaks 8.28.0
scanned all 181 retained commits before the release-candidate change. Its 18 findings were reviewed
as six synthetic test/E2E identifiers, one deliberately malformed private-key fixture, or eleven
SDD/ADR diagram labels. `.gitleaksignore` records only their exact history and current-tree
fingerprints. The scans must run again on the exact merged candidate before publication. The
reviewed allowlist SHA-256 is
`f868ccc6229550871462764720d0fe3ee98dc170e7a9dcca7cba40d5e75bdc8e`.

## Summary of blockers and decisions

| Area | Redacted result | Status / owner decision required |
| --- | --- | --- |
| Credential filenames and secret material | Gitleaks 8.28.0 found the same 18 reviewed matches in history and the current tree: six test/E2E identifier fixtures, eleven SDD/ADR diagram labels, and one deliberately malformed private-key fixture. Raw values are withheld. | **APPROVED:** the owner accepted paired exact history/current-tree fingerprints; no rule, directory, or commit-wide exclusion is allowed. The final candidate must pass both scans with zero unallowlisted findings. |
| Private endpoints and IP addresses | Reviewed matches are documented local defaults, LAN deployment guidance, reserved test networks, and negative security examples. | **APPROVED:** only the reviewed local/LAN/test uses are accepted. |
| Personal filesystem paths | Reviewed examples are documented unsafe-path cases or container/service-account paths. | **APPROVED:** no personal workstation path is accepted as product configuration. |
| Current-tree email-like strings | Seventy files contain email-shaped values. Of 194 unique values, 192 use reserved fixture domains; the other two are a product placeholder and a synthetic test identity. | **APPROVED:** no maintainer address is introduced by the release preparation. |
| Git author emails | Retained history contains the repository owner's GitHub noreply and personal author addresses. | **APPROVED:** on 2026-09-18 the owner explicitly accepted public exposure and confirmed the author identity is theirs. |
| Asset and license provenance | First-party logo/social assets were approved by the owner. Vendored Geist and JetBrains Mono files retain their exact upstream copyright and SIL OFL 1.1 texts beside the binaries. | **RESOLVED:** the two upstream `OFL.txt` files are part of the release candidate. |
| Repository and package namespace migration | Repository, workflows, images, installer/build code, release contracts, and public links use `latentrun/SurgePilot` and `ghcr.io/latentrun/*`. | **RESOLVED:** the public namespace and package visibility were validated before release preparation. |
| Immutable authorship baseline | `v1.0.0` is the owner-selected original public baseline and is recorded in `AI-AUTHORSHIP.md`. | **SELECTED:** publication still requires a green exact-candidate validation tag and create-only Release workflow. |
| Public surfaces | Repository, Pages, localized docs, and the three GHCR package namespaces are public. No semantic GitHub Release exists yet. | **READY FOR VALIDATION:** no Demo link may imply that an unrecorded video exists. |

## Review evidence

Store scanner output under a private temporary directory and report only reviewed classifications. The final review must distinguish supported local/LAN examples and container service accounts from real private deployment coordinates or personal developer paths. A pattern hit is not an automatic deletion decision. Namespace results must be resolved with the release contracts because several strings are create-only publication invariants, not ordinary documentation links.

## Required follow-up before `v1.0.0`

1. Re-run Gitleaks 8.28.0 history and current-tree scans against the exact merged candidate with
   the reviewed fingerprint file; require zero unallowlisted findings and retain only the redacted
   summary.
2. Run `make verify`, the full validation-tag release path, docs/browser checks, and release
   contracts on the exact candidate.
3. Verify that `v1.0.0`, its GitHub Release, and all three semantic GHCR tags remain absent.
4. Create the annotated tag locally on the validated commit, verify its target, then push it once.
5. Wait for the create-only Release workflow and anonymously verify the installer, bundle,
   checksums, manifests, Runtime assets, and digest-backed GHCR images.

## Change boundary

This audit never authorizes automatic deletion, replacement, history rewriting, or credential
rotation. Any future non-synthetic finding stops release and requires a separate owner decision.

## Final audit backfill

- Final tree path comparison was performed directly against the immutable source snapshot. The
  candidate had five staging-only paths; all five were removed as obsolete support/test workflow
  files: `.github/workflows/verify.yml`,
  `apps/api/tests/test_p0_03_runtime_bootstrap_config.py`,
  `apps/api/tests/test_p1_00_monitoring_worker.py`,
  `apps/api/tests/test_p2_01_openapi_step_generation.py`, and
  `tests/contract/test_p1_03_env_compose_drift.py`. No source path is omitted, and `uv.lock` is
  retained.
- No reconstruction support files were added to the product tree. The final tree therefore has no
  unrecorded support-file exception.
- Current-tree cleanup scans found no previous-owner namespace, old-branch path, old checkpoint
  identifier, old history-size count, or repository-agent tooling reference. Existing source
  content, release contracts, Runtime behavior, and product execution contracts were otherwise
  left intact.
