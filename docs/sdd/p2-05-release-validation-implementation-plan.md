# P2-05 Development Release Validation Implementation Plan

**Execution status:** The reserved-version guard and `.github/workflows/release-validation.yml` are
implemented; final job names and the acceptance/evidence matrix are recorded in
`docs/sdd/slices/P2-05-cross-platform-distribution.md` §19.

**Goal:** Add one minimal GitHub Actions workflow that validates P2-05 on pull requests and performs an explicit public GHCR multi-architecture validation from trusted `validation-*` tags without creating a public release.

**Architecture:** Keep `.github/workflows/release.yml` as the production create-only workflow. Add `.github/workflows/release-validation.yml` with separate read-only PR jobs and package-writing validation-tag jobs, reusing the existing Runtime builder, image Dockerfiles, release bundle builder, release wrapper, and release-stack verifier. Reserve `v0.0.0` for local validation artifacts and reject it in the production release preflight.

**Tech Stack:** GitHub Actions, Docker Buildx/GHCR, POSIX shell/Bash workflow blocks, Python/pytest contract tests, existing Make verification targets.

## Global Constraints

- Pull-request jobs use only `contents: read` and `packages: read`; they never push images.
- Package writes occur only for `validation-<12-to-40 lowercase hex>` tags whose suffix matches the tagged SHA and whose commit is contained in `origin/main`.
- Git validation tags may use a commit prefix; GHCR validation tags always use the full `GITHUB_SHA`.
- Validation reruns may replace only `validation-<full-sha>[-arch]`; they never write `v*`, `package-bootstrap`, or operator-selected package tags.
- Validation Runtime and bundle version is exactly `v0.0.0`; production release preflight rejects `v0.0.0`.
- Smoke jobs pre-position matching Runtime files in `.surgepilot/runtime-artifacts/` and must not create or download from a GitHub Release.
- Reuse current Dockerfiles, scripts, Compose, and verification targets; do not add reusable workflows, sandbox repositories, package namespaces, retention automation, API/DB/Web behavior, or P2-02 scope.

---

### Task 1: Add failing workflow contract tests

**Files:**
- Modify: `tests/contract/test_p2_05_distribution.py`

**Interfaces:**
- Consumes: P2-05 §14.1 and §19 contracts.
- Produces: textual/YAML contract checks for the production reserved-version guard and the new validation workflow.

- [x] **Step 1: Write failing tests**

Add tests that require:

```python
def test_formal_release_rejects_reserved_validation_version() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    preflight = workflow.split("\n  preflight:\n", 1)[1].split("\n  verify:\n", 1)[0]
    assert 'test "$TAG" != "v0.0.0"' in preflight


def test_development_release_validation_workflow_contract() -> None:
    path = ROOT / ".github/workflows/release-validation.yml"
    workflow = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)
    assert parsed[True]["pull_request"]["branches"] == ["main"]
    assert parsed[True]["push"]["tags"] == ["validation-*"]
    assert "ubuntu-24.04-arm" in workflow
    assert "fetch-depth: 0" in workflow
    assert "refs/remotes/origin/main" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "fail-fast: false" in workflow
    assert 'TAG="validation-$GITHUB_SHA"' in workflow
    assert 'ARCH_TAG="$TAG-${{ matrix.arch }}"' in workflow
    assert '--fixed-version "v0.0.0"' in workflow
    assert '--version "v0.0.0"' in workflow
    assert "surgepilot/.surgepilot/runtime-artifacts" in workflow
    assert 'DOCKER_CONFIG="$anonymous_config"' in workflow
    assert "gh release" not in workflow
```

Also assert that PR native builds use `--load`, validation publication uses `--push`, only validation publication jobs contain `packages: write`, and package tag commands never target `package-bootstrap` or a `v*` tag.

- [x] **Step 2: Verify RED**

Run:

```bash
uv run --all-packages pytest tests/contract/test_p2_05_distribution.py -q
```

Expected: FAIL because `.github/workflows/release-validation.yml` does not exist and production release does not yet reject `v0.0.0`.

### Task 2: Implement the reserved-version guard and validation workflow

**Files:**
- Modify: `.github/workflows/release.yml`
- Create: `.github/workflows/release-validation.yml`
- Test: `tests/contract/test_p2_05_distribution.py`

**Interfaces:**
- Consumes: `scripts/run_runtime_builder.py`, `scripts/build_release_bundle.py`, `infra/release/*`, and `make verify-p2-05-release-stack`.
- Produces: PR verification jobs and trusted validation-tag GHCR/release-stack evidence.

- [x] **Step 1: Reject the reserved production version**

Immediately after the exact SemVer check in the production preflight, add:

```bash
test "$TAG" != "v0.0.0" || {
  echo "v0.0.0 is reserved for development validation and cannot be published."
  exit 1
}
```

- [x] **Step 2: Add read-only verification and PR native jobs**

Create `.github/workflows/release-validation.yml` with:

```yaml
on:
  pull_request:
    branches: [main]
  push:
    tags: ["validation-*"]

permissions:
  contents: read
  packages: read
```

Add one `verify` job that runs the existing setup, contract generation, and `make verify` path. Add a `pr-native` amd64/arm64 matrix with `fail-fast: false`; each native runner builds Runtime `v0.0.0`, runs `make verify-runtime-compat`, and builds API/Web/Demo images with single-platform `--load` and no registry login.

- [x] **Step 3: Add trusted validation-tag preflight**

The tag preflight must checkout with `fetch-depth: 0`, explicitly fetch `main`, validate the tag prefix and SHA, prove ancestry, and anonymously inspect each `package-bootstrap` tag before allowing package writes:

```bash
git fetch --no-tags --force origin main:refs/remotes/origin/main
suffix=${GITHUB_REF_NAME#validation-}
[[ "$GITHUB_REF_NAME" =~ ^validation-[0-9a-f]{12,40}$ ]]
[[ "$GITHUB_SHA" == "$suffix"* ]]
git merge-base --is-ancestor "$GITHUB_SHA" refs/remotes/origin/main
```

- [x] **Step 4: Add native Runtime/image publication jobs**

Use native amd64/arm64 runners with `packages: write`. Build Runtime assets using fixed version `v0.0.0`, run compatibility checks, upload the Runtime files, and push the three images only as:

```bash
TAG="validation-$GITHUB_SHA"
ARCH_TAG="$TAG-${{ matrix.arch }}"
```

Use the existing Dockerfiles and version/revision OCI build arguments.

- [x] **Step 5: Add index, bundle, and smoke jobs**

Create the three multi-architecture `validation-$GITHUB_SHA` indexes from their native tags, verify both platforms, and upload `image-digests.json`. Assemble `surgepilot-v0.0.0.tar.gz` with the existing bundle builder and both Runtime artifacts. In each native smoke job:

```bash
tar -xzf release-assets/surgepilot-v0.0.0.tar.gz
mkdir -p surgepilot/.surgepilot/runtime-artifacts
cp release-assets/surgepilot-runtime-linux-$RELEASE_ARCH-v0.0.0.* \
  surgepilot/.surgepilot/runtime-artifacts/
./surgepilot up
make verify-p2-05-release-stack
```

Before `up`, anonymously inspect all recorded digests using an empty temporary Docker configuration. Do not add a publish or GitHub Release job.

- [x] **Step 6: Verify GREEN**

Run:

```bash
uv run --all-packages pytest tests/contract/test_p2_05_distribution.py -q
```

Expected: PASS.

### Task 3: Validate syntax, contracts, and documentation facts

**Files:**
- Modify: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- Test: `.github/workflows/release-validation.yml`
- Test: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: completed workflow job names and final behavior.
- Produces: implementation backfill and syntax evidence.

- [x] **Step 1: Backfill exact implementation facts**

Update §19 with final job names, the `v0.0.0` production guard, Runtime artifact handoff, and the commands used for focused verification. Do not expand product scope.

- [x] **Step 2: Parse YAML and Bash blocks**

Run a Python/PyYAML check that loads both workflows and passes every `run` block to `bash -n`. Also run:

```bash
sh -n infra/release/surgepilot
git diff --check
```

Expected: all commands exit zero.

- [x] **Step 3: Run focused regression tests**

Run:

```bash
uv run --all-packages pytest \
  tests/contract/test_p2_05_distribution.py \
  tests/test_release_runtime_artifact.py \
  tests/test_release_preflight.py \
  tests/test_release_wrapper.py -q
```

Expected: PASS.

### Task 4: Final verification and recorded evidence

**Files:**
- Verify: `.github/workflows/release.yml`, `.github/workflows/release-validation.yml`, and the
  P2-05 Slice record.

**Interfaces:**
- Consumes: the completed release-validation implementation and its verification evidence.
- Produces: the recorded release-validation acceptance evidence.

- [x] **Step 1: Run final repository gates**

```bash
make generate-contracts
make verify
make verify-runtime-compat
make verify-e2e
```

Expected: all commands exit zero.

- [x] **Step 2: Confirm the release-validation acceptance facts**

Confirm exact §19 compliance, job permissions, tag trust/ancestry, absence of package writes from
read-only pull-request jobs, GHCR tag derivation, Runtime local reuse, anonymous digest access,
`v0.0.0` rejection, and the absence of a public Release.

- [x] **Step 3: Re-run the affected gates after a confirmed defect**

Any correctness, security, or documented-behavior defect must be fixed and the affected gates
re-run before the release-validation surface is accepted.

---

Reconstruction verification backfill: the implemented release-validation surface is the reserved
`v0.0.0` production guard plus `.github/workflows/release-validation.yml`; final job names, the
`main`-ancestry tag trust rules, and the acceptance/evidence matrix are recorded in
`docs/sdd/slices/P2-05-cross-platform-distribution.md` §19. Focused verification is
`tests/contract/test_p2_05_distribution.py` together with `tests/test_release_runtime_artifact.py`,
`tests/test_release_preflight.py`, and `tests/test_release_wrapper.py`, with
`make generate-contracts` and `make verify` as repository gates. The Runtime fetch, builder, and
release-stack paths stay consistent with the published P2-05 artifacts through
`scripts/fetch_runtime_release.py`, `scripts/run_runtime_builder.py`,
`scripts/release_runtime_artifact.py`, and `make verify-p2-05-release-stack`.

Runtime identity backfill: the reconstructed Load Node and Run Runtime identity chain is the frozen
migration sequence `0016_p2_02` -> `0017_p2_03` -> `0018_p1_09` ->
`0019_p2_02_ssh_host_key` -> `0020_p0_runtime_version` -> `0021_p0_run_allocation_runtime`.
`0019_p2_02_load_node_ssh_host_key_trust.py` adds `ssh_host_key_algorithm`,
`ssh_host_key_public_key`, `ssh_host_key_fingerprint_sha256`, `ssh_host_key_trusted_at`, and
`ssh_host_key_trusted_by` to `load_nodes`, constrains `ssh_host_key_trusted_by` to `users.id`, and
resets every non-archived, non-disabled node to `uninitialized` with
`LOAD_NODE_SSH_HOST_KEY_UNTRUSTED`; `0020_p0_runtime_version.py` adds nullable `runtime_version` to
`load_nodes` and `load_node_initialization_attempts`; and `0021_p0_run_allocation_runtime.py` adds
nullable `expected_runtime_version` to `run_node_allocations` and refuses to upgrade while any Run
is `initializing`, `running`, or `stopping`. The matching mapped columns are in
`apps/api/app/models/load_nodes.py` (the `ssh_host_key_*` fields plus `runtime_version` on both the
node and the initialization attempt) and `apps/api/app/models/runs.py` (`expected_runtime_version`
on the allocation). Migration verification is
`apps/api/tests/test_p0_04_runtime_identity_migration.py` for the active-Run refusal and the
untouched legacy allocation and `apps/api/tests/test_p0_07_migrations.py` for the SQLite upgrade
path, together with the Load Node initialization, allocation, Runner protocol, and release
verification suites recorded in the P2-05 Slice.

Remaining risks: native amd64/arm64 Runtime and image construction, anonymous GHCR digest access,
and the digest-pinned release-stack smoke need native runners and are environment- or release-gated;
the first real `vX.Y.Z` public Runtime download, semantic create-only conflict handling, and
Draft-to-final Release ordering remain proven only by that first release; the `0021` allocation
column stays nullable for legacy terminal allocations, so a callback without a matching persisted
expected version fails closed with `RUNNER_RUNTIME_MISMATCH`; and Apple Silicon Docker Desktop
remains a manual acceptance item. The reconstruction publishes as `latentrun/SurgePilot` on
`main` with `ghcr.io/latentrun/*` images, so frozen previous-owner and non-`main` branch references
are deliberately rewritten.
