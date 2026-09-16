# P0 Runtime Bootstrap Packaging Plan

- Document status: Draft baseline
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/p0-runtime-bootstrap-plan.md`
- Scope of application: P0 Load Node initialization, Runtime packaging, Runner execution, Taurus/JMeter path convergence
- Source scheme: `package.md` / Runtime Bootstrap scheme provided by the user

---

## 1. Goal

P0 uses the self-contained runtime tar package generated during the release phase to replace the pre-installed Taurus, JMeter and JMeter plugins on each Load Node.

The goals of Runtime Bootstrap are:

1. Make Load Node initialization repeatable, verifiable, and failure-safe.
2. Let P0 Run execution not depend on `bzt` or `jmeter` in system `PATH`.
3. Let Taurus YAML explicitly use JMeter in the current Load Node's runtime.
4. Keep the init phase with zero network, zero pip, and zero compilation.

Runtime Bootstrap is P0 execution closed-loop support, not a productized runtime management capability.

---

## 2. P0 range

### 2.1 In Scope

P0 implementation:

1. Build a runtime tar package on the current packaging machine architecture.
2. api-worker reads the runtime package from the local read-only directory.
3. api-worker selects matching artifacts based on the target Load Node architecture.
4. api-worker pushes the runtime package through SFTP `upload_stream`.
5. The Load Node side performs SHA256 verification, secure decompression, metadata verification, availability check and atomic activation of the entire package.
6. Runner uses `bzt` in runtime.
7. Taurus YAML dynamically writes the JMeter path in the runtime of the current Load Node.

### 2.2 Out of Scope

P0 does not implement:

1. Runtime UI.
2. Runtime catalog.
3. User uploads runtime.
4. Multi-version negotiation.
5. Grayscale release.
6. Automatic rollback.
7. The old runtime is automatically cleaned.
8. per-file checksum manifest.
9. Runtime catalog or UI-driven glibc comparison; release compatibility is covered by the Ubuntu 24.04 + Debian 12 `make verify-runtime-compat` matrix.
10. qemu cross-architecture smoke.
11. A single release forces the dual-architecture runtime to be built at the same time.
12. Block network test.
13. MinIO storage runtime.
14. Node local `pip install` Taurus.
15. Automatically install Java, system Python, tar or OS packages.

The meaning of P0 not implementing automatic rollback is: Runtime Bootstrap, product UI, API, api-worker and Load Node initialization logic are not responsible for automatically switching back to the old version after the new runtime fails, automatically restoring the deployment configuration, automatic cleaning or automatic grayscale/rollback orchestration.

If deployment requires switching or rolling back the runtime version, the content of the api-worker local artifact directory or `LOAD_NODE_RUNTIME_VERSION` can only be adjusted by the external deployment process. This is a deployment operation, not the Runtime Bootstrap product capability, nor the automatic rollback capability of the initialization logic.

---

## 3. Architecture strategy

Runtime artifacts are bound to the packaging machine architecture. P0 does not do cross-architecture builds.

Schema mapping:

```text
x86_64 -> linux-amd64
amd64 -> linux-amd64
aarch64 -> linux-arm64
arm64 -> linux-arm64
```

Release artifact:

```text
surgepilot-runtime-linux-<arch>-<version>.tar.gz
surgepilot-runtime-linux-<arch>-<version>.tar.gz.sha256
```

Deployment rules:

1. If a deployment only supports `amd64` Load Node, only the `linux-amd64` artifact will be released.
2. If a certain deployment only supports `arm64` Load Node, only the `linux-arm64` artifact will be released.
3. If the same environment needs to support two types of Load Nodes, you can generate artifacts on the two types of packaging machines and put them into the same api-worker local artifact directory.
4. Load Node must execute `uname -m` when initializing, and only select local artifacts that match the architecture.
5. When the target Load Node architecture does not match the artifact, the initialization fails; it must not be downgraded to the system Taurus/JMeter, and it must not be downloaded online.

---

## 4. Runtime Artifact

Runtime builds use a multi-stage Docker build or equivalent release build:

1. `runtime-builder`: Use `uv` to obtain python-build-standalone CPython, install Taurus, download JMeter, put in fixed plug-ins, generate metadata, and package runtime.
2. `runtime-artifact`: Unzip the runtime tar package in a new path or clean stage and execute smoke, then export the tar package and its `*.tar.gz.sha256` sidecar.
3. `ssh-load-node`: SSH E2E and compatibility images consume the production runtime tar package; they do not create a separate runtime artifact source.

The runtime package must directly contain the complete CPython directory, not just the package venv, and does not rely on the node system Python execution `bzt`.

The default target version of Python in the runtime is `3.12.x`. If Taurus `1.16.50` builds under Python 3.12 or smoke fails, fallback to Python `3.11.x` is allowed, but must be logged in ADR and metadata.

The runtime package contains:

1. `python/`: Complete python-build-standalone CPython.
2. Taurus `1.16.50` and complete Python dependency closure.
3. `apache-jmeter-5.6.3/`.
4. The current generated Taurus/JMX closure requires exactly `jpgc-casutg`, `jpgc-json`,
   `jpgc-tst`, `bzm-random-csv`, and `jmeter-plugin-influxdb2-listener`; plugins for JMX
   elements that SurgePilot does not generate are not packaged.
5. `bin/bzt`: Call CPython/Taurus in runtime.
6. `metadata.json`.
7. The whole-archive `*.tar.gz.sha256` sidecar.

The runtime package does not contain an SSH test user, sshd configuration, E2E-only debug tools, OS package manager cache, Load Node SSH credentials, Workspace data, or MinIO artifacts.

`metadata.json` Example:

```json
{
  "name": "surgepilot-runtime",
  "version": "<version>",
  "platform": "linux",
  "arch": "amd64",
  "python": "3.12.x",
  "taurus": "1.16.50",
  "jmeter": "5.6.3",
  "plugins": [
    "jpgc-casutg",
    "jpgc-json",
    "jpgc-tst",
    "bzm-random-csv",
    "jmeter-plugin-influxdb2-listener"
  ],
  "builder": {
    "os": "<builder-os>",
    "arch": "amd64"
  }
}
```

Metadata rules:

1. `arch` can only be `amd64` or `arm64`.
2. `metadata.arch` must be consistent with the file name and target Load Node probe schema.
3. `builder.arch` must record the packaging machine architecture.
4. When the Python version rolls back to `3.11.x`, metadata and ADR must record the reason synchronously.

Building access control must be executed in the "new path after decompression" or "clean stage":

```bash
<extracted-runtime>/bin/bzt -h
```

Minimal JMeter smoke must also be performed, and smoke must use the JMeter path within the runtime and is not allowed to reference system JMeter.

---

## 5. Runtime storage and publishing

api-worker local read-only directory:

```text
/opt/surgepilot/runtime-artifacts/
```

Configuration items:

```text
LOAD_NODE_RUNTIME_ARTIFACT_DIR=/opt/surgepilot/runtime-artifacts
LOAD_NODE_RUNTIME_VERSION=<version>
LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS=<seconds>
```

Storage rules:

1. api-worker only reads this directory and does not modify it.
2. This directory is written by the deployment process. It is recommended that the root or publishing user be writable and api-worker be read-only.
3. The runtime does not include MinIO.
4. runtime is not a Workspace Dependency File, nor is it a Run artifact.
5. Only one architecture artifact supported by the current deployment can exist in the directory.
6. If multiple schema artifacts exist in the directory, the initialization is selected based on the target Load Node schema.

Deploy link rules:

1. The release job builds the runtime tar package and its `*.tar.gz.sha256` sidecar on the target architecture packaging machine.
2. Release job executes decompression new path smoke and minimum JMeter smoke.
3. The release job publishes the artifact to the platform release product repository.
4. The deployment process puts the artifacts required by the target environment into the api-worker local read-only directory.
5. Verify that the configured runtime version exists in the local directory before starting or initializing the api-worker.
6. Version switching or rollback is only allowed by the deployment process to adjust the local directory content or `LOAD_NODE_RUNTIME_VERSION`; this is not the Runtime Bootstrap automatic rollback capability.

Permission suggestions:

```bash
sudo mkdir -p /opt/surgepilot/runtime-artifacts
sudo chown root:surgepilot /opt/surgepilot/runtime-artifacts
sudo chmod 0750 /opt/surgepilot/runtime-artifacts
sudo chown root:surgepilot /opt/surgepilot/runtime-artifacts/surgepilot-runtime-linux-*-<version>.tar.gz
sudo chown root:surgepilot /opt/surgepilot/runtime-artifacts/surgepilot-runtime-linux-*-<version>.tar.gz.sha256
sudo chmod 0640 /opt/surgepilot/runtime-artifacts/surgepilot-runtime-linux-*-<version>.tar.gz
sudo chmod 0640 /opt/surgepilot/runtime-artifacts/surgepilot-runtime-linux-*-<version>.tar.gz.sha256
```

Specific users and groups can be adjusted according to the deployment environment, but the invariants are: the deployment process is writable, api-worker is read-only, and the Load Node does not directly access the directory.

---

## 6. Load Node basic dependencies

The following evidence must be recorded with the real target Load Node before freezing:

```text
uname -m
cat /etc/os-release
java -version
python3 --version
tar --version
```

P0 default baseline:

```text
Ubuntu >= 24.04 or Debian >= 12
tar
java >= 11, recommended Java 17
python3 >= 3.12 for SurgePilot runner.py
```

Load Node no longer requires Taurus, JMeter, JMeter plugins, pip, gcc, python3-dev to be installed.

Python boundaries:

1. Python for Taurus comes from the runtime package.
2. Node system Python is only available for SurgePilot `runner.py`.
3. If the real node baseline is lower than the default requirement, the baseline decision in ADR/P0-03 must be updated first, and the completion cannot be automatically installed during the init phase.

---

## 7. Initialization process

Executed when api-worker initializes Load Node:

1. Connect to the Load Node.
2. Check the base dependencies and `runnerHome`.
3. Execute the `uname -m` probe architecture.
4. Select the corresponding runtime tar package from the local read-only directory.
5. If the corresponding architecture artifact does not exist, initialization fails and a security error message is logged.
6. Upload to `runnerHome/tmp/` via SFTP `upload_stream`.
7. Verify the entire packet SHA256.
8. Safely decompress to a temporary directory to prevent path traversal.
9. Verify version, arch, and component versions of `metadata.json`.
10. Check that key files exist.
11. Execute `bzt -h` in runtime.
12. Execute `jmeter --version` in runtime.
13. Check that all five required plugin jars are valid archives and contain their contract classes.
14. After passing the verification, move to `runnerHome/runtimes/<version>/`.
15. Atomic update `runnerHome/current -> runnerHome/runtimes/<version>` .
16. Upload or verify the Runner bundle.
17. Detect Runner version.
18. Tag initialization successful.

Failure rules:

1. Do not modify the existing `current` when any step fails.
2. The definition of successful initialization is that the runtime is available.
3. System `bzt --help` or system JMeter cannot be used as the basis for successful initialization.

---

## 8. Init hard rules

Prohibited during Init phase:

```text
pip install
python -m pip install
apt install
curl
wget
online plugin install
native extension compile
```

Init phase reserved:

```text
whole archive SHA256
safe extract
metadata validation
runtime bzt -h
runtime jmeter --version
five-plugin jar/class validation
atomic symlink
```

---

## 9. Taurus configuration

The main line of defense against automatic downloads by Taurus is to generate YAML that explicitly overrides `modules.jmeter.path` .

`TAURUS_DISABLE_DOWNLOADS` cannot be used as the main anti-download mechanism; may be deleted or retained only as defense-in-depth and shall not be used as an acceptance condition.

Taurus YAML example:

```yaml
modules:
  jmeter:
    path: <runnerHome>/current/apache-jmeter-5.6.3/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    fix-log4j: false
    fix-jars: false
    force-ctg: false
```

Rules:

1. `jmeter.path` must be dynamically derived according to the Load Node selected in this run.
2. No longer use global `settings.load_node_jmeter_path` as a fixed value for all nodes.
3. To implement, you only need to pass in the `runner_home` parameter to `build_*_execution_bundle` and splice the paths.
4. Do not design complex path services.
5. `force-ctg` defaults to false.
6. Set true only if the scenario uses `steps` and a Concurrent Thread Group is really needed.

---

## 10. Runner execution

Runner is no longer executed:

```bash
bzt surgepilot.yml
```

Runner executes instead:

```bash
${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml
```

Rules:

1. `RUNNER_HOME` is injected by api-worker.
2. `-n` is used to skip `/etc/bzt.d` and `~/.bzt-rc`.
3. `-n` is defense-in-depth, not the main anti-download mechanism.
4. Runner does not depend on the system `PATH` to find `bzt`.
5. The Runner does not read the api-worker internal code, but only receives the necessary paths through the contract and execution bundle.

---

## 11. Code convergence items

Subsequent code convergence items recorded in this plan include:

1. `load_node_initializer.py` Delete system `bzt --help` Initialize success conditions, install and verify `runnerHome/current/bin/bzt`.
2. `config.py` adds `LOAD_NODE_RUNTIME_ARTIFACT_DIR`, `LOAD_NODE_RUNTIME_VERSION`, `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS`.
3. Execute bundle builder to change `modules.jmeter.path` to dynamically write according to the current Load Node `runnerHome`.
4. Runner executes `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml`.

Runtime Bootstrap implementation PRs must update code, tests, and this document when implementation facts change.

---

## 12. Idempotent and failsafe

Rules:

1. When the target runtime is installed and the metadata/version/arch verification passes, uploading and installation are skipped.
2. Failure in uploading, SHA256, decompression, metadata, `bzt -h`, `jmeter --version`, and plug-in check will not affect the existing `current`.
3. Switch `current` only after complete verification is passed.
4. `current` switches to using atomic symlink.
5. Use `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS` for runtime installation.

---

## 13. Security requirements

Must implement:

1. SHA256 verification of the entire package.
2. Safe decompression against absolute path, `..` path traversal, symlink escape and writing out `runnerHome`.
3. Use secure quoting for remote commands.
4. Runtime installation process must not write `runnerHome`.
5. Do not deliver the runtime download URL or download credentials to the node.
6. Do not expose SSH credentials, internal paths, or sensitive configuration to user-visible logs.
7. The initialization log only records the security summary and stable error codes, but does not record the complete internal artifact directory.

---

## 14. Document carrying requirements

Must be synchronized before development:

1. ADR records uv-built self-contained runtime, push model, local read-only artifact dir, packaging machine architecture product strategy, arch/glibc/ABI binding, init three zero, and build access control.
2. `00-product-scope-and-priority.md` makes it clear that Runtime Bootstrap is P0 execution closed-loop support, not a runtime management product capability.
3. `P0-03-load-nodes.md` Add the Runtime Bootstrap chapter and replace the system Taurus/JMeter pre-installed caliber.
4. This document records the link, permissions, and deployment process version switching boundaries from release artifact to `/opt/surgepilot/runtime-artifacts/`.
5. Real Load Node baseline evidence has been recorded.

---

## 15. Acceptance Criteria

### 15.1 Document Acceptance

1. ADR has recorded the key decisions of the program.
2. The Scope document has clarified the P0 boundary.
3. P0-03 has recorded the Runtime Bootstrap initialization boundary.
4. This solution document has recorded the local read-only artifact directory link, permissions, and deployment process version switching boundaries.
5. Real Load Node baseline evidence has been recorded.

### 15.2 Build acceptance

1. Produce the corresponding runtime tar package on the current packaging machine architecture.
2. The tar package file name, metadata, and packaging machine architecture are consistent.
3. The tar package contains the CPython interpreter itself, not just venv.
4. `bzt -h` passes the new path or clean stage after decompression.
5. Minimal JMeter smoke passes through new path or clean stage after decompression.

### 15.3 Initialization acceptance

1. api-worker reads the runtime from the local read-only directory.
2. api-worker selects matching artifacts based on the target Load Node architecture.
3. api-worker uses `upload_stream` to push runtime.
4. Zero network, zero pip, and zero compilation in the init stage.
5. Installation failure does not destroy the existing `current`.

### 15.4 Perform acceptance

1. Runner uses `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml`.
2. Taurus YAML writes `modules.jmeter.path` as `<runnerHome>/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper`, beside the real JMeter executable so Taurus derives the correct JMeter home and `lib/ext`.
3. Execution does not depend on `bzt` or `jmeter` in system `PATH`.
4. Execute without using Taurus default `~/.bzt/jmeter-taurus/...`.

---

## 16. Implementation Backfill

This PR implements the code convergence items from §11.

Implementation facts:

1. `apps/api/app/core/config.py` now reads `LOAD_NODE_RUNTIME_ARTIFACT_DIR`, `LOAD_NODE_RUNTIME_VERSION`, and `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS`.
2. `apps/api/app/services/load_node_initializer.py` no longer treats system `bzt --help` or a global system JMeter path as initialization success criteria. It probes `uname -m`, selects the matching local runtime artifact, uploads it with SFTP `upload_stream`, verifies whole-archive SHA256, safely extracts under `runnerHome` while rejecting symlink/path traversal escapes, validates `metadata.json` including a supported Python version, verifies self-contained runtime critical files, probes runtime-contained `bin/bzt -h` and JMeter `--version`, checks the required plugin jar as a non-empty zip/jar, and atomically activates `runnerHome/current` with retry-safe stale-target replacement. A damaged active same-version target is exchanged with the fully validated staged candidate and then removed. The already-installed skip path also revalidates runtime metadata, critical files, runtime `bzt`, runtime JMeter, and the required plugin before skipping upload.
3. Execution bundle generation receives the selected node `runnerHome` and writes `modules.jmeter.path` as `<runnerHome>/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper`. The wrapper delegates to the adjacent real JMeter executable and preserves Taurus' JMeter-home/plugin detection. Generated YAML is self-contained for Runner's `bzt -n` mode: it declares the `local`, `jmeter`, `consolidator`, `final-stats`, `console`, and `passfail` module classes it uses, plus the HTTP protocol handler and `settings.aggregator`; JMeter fix/download-related mutation flags are pinned off with `fix-log4j: false`, `fix-jars: false`, `detect-plugins: false`, and default `force-ctg: false`.
4. Runner starts Taurus with `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml` and no longer resolves `bzt` through system `PATH`.
5. Docker Compose wires the api-worker runtime artifact directory as a read-only mount and passes the runtime version/install timeout environment.
6. E2E verification builds or reuses the `p0-e2e` Runtime through `scripts/run_runtime_builder.py --fixed-version`, which invokes the production `scripts/release_runtime_artifact.py` recipe inside native Linux. SSH E2E, source startup, compatibility verification, and tagged release jobs share one source, packaging flow, manifest, SHA256, and reuse invariant.
7. Runtime Bootstrap error codes are exported through the OpenAPI `x-surgepilot-error-codes` registry.
8. Successful initialization persists the activated metadata version as Load Node `runtimeVersion`. Selection and allocation require it to equal `LOAD_NODE_RUNTIME_VERSION`, and remote Run start revalidates `current/metadata.json` before uploading Runner, bundle, environment, or secret material.

New/updated verification coverage:

1. Unit tests cover runtime settings, architecture mapping, missing/empty/unsupported architecture output, missing artifact/checksum behavior, SFTP stream upload, safe extraction symlink escape rejection, retry-safe stale target activation, runtime self-contained file checks, metadata Python validation, plugin zip validation, no system Taurus/JMeter checks, init hard-rule command absence, stable runtime error codes, and OpenAPI runtime error-code export.
2. Run control and service tests cover generated debug and test-plan Taurus YAML using the selected node runtime JMeter path and the self-contained Taurus module aliases required by `bzt -n`.
3. Runner tests cover `current/bin/bzt -n surgepilot.yml` and prove a `PATH` `bzt` is not used.
4. E2E verifier tests cover production runtime artifact preparation before Compose startup, runtime environment propagation, and remote assertions that `current/bin/bzt`, runtime JMeter, and non-`~/.bzt/jmeter-taurus` bundle paths are used.

Official startup preflight implementation backfill:

1. `make release-runtime` provides the no-CI local release-job subset through the Linux builder container. It builds or reuses the Docker-daemon architecture under `.surgepilot/runtime-artifacts/default`, computes `version` as `dev-<manifestHash>` or `<RUNTIME_RELEASE_PREFIX>-<manifestHash>`, and writes a host-correct runtime env file consumed by official startup.
2. The stable manifest hash is computed from normalized inputs, including builder recipe files, runner wrapper code, target architecture, release prefix, and component versions/checksums. For default local builds the component checksums are the actual downloaded or cached files; release operators may also pin expected component checksums through `RUNTIME_JMETER_SHA256`, `RUNTIME_CASUTG_SHA256`, and `RUNTIME_INFLUXDB2_LISTENER_SHA256`, which fail fast on mismatch. Test-only source-dir packaging additionally hashes the supplied source tree. The final `.tar.gz` checksum remains an integrity sidecar and is not an input to version generation.
3. Artifact reuse requires computing the current component inputs/checksums first, then matching the resulting manifest hash, target architecture, archive plus `*.tar.gz.sha256` sidecar, metadata version/architecture, and a valid whole-archive SHA256 digest. Reuse is never based on filename alone and cannot bypass current component checksum calculation.
4. `make start-full-stack` and `make restart-full-stack` run runtime preflight by default, inject the same `LOAD_NODE_RUNTIME_VERSION` and repo-local host artifact directory into `api` and `api-worker`, validate full Compose config, and fail fast on runtime or compose config errors. `SURGEPILOT_SKIP_RUNTIME_PREFLIGHT=1` remains a manual/debug opt-out only.
5. Runtime artifacts remain deployment assets and are not added to MinIO, Dependency Files, Run artifacts, runtime UI/catalog/API, gray release, rollback, or cleanup product capabilities.

Remaining constraints:

1. Release-grade artifacts remain a deployment/release concern governed by ADR-0007. `infra/docker/runtime-builder/Dockerfile` provides Linux prerequisites, `scripts/run_runtime_builder.py` provides host/Docker orchestration, and `scripts/release_runtime_artifact.py` remains the underlying python-build-standalone, Taurus, JMeter, plugin, manifest, checksum, and reuse implementation. SSH E2E uses the same containerized builder with fixed version `p0-e2e`.
2. Runtime version switching/rollback remains external deployment behavior only.

---

## 17. Reconstruction Verification Backfill

The runtime-identity persistence described in §16 item 8 is carried by the frozen migration chain
`0016_p2_02` -> `0017_p2_03` -> `0018_p1_09` -> `0019_p2_02_ssh_host_key` ->
`0020_p0_runtime_version` -> `0021_p0_run_allocation_runtime`:

1. `0019_p2_02_load_node_ssh_host_key_trust.py` adds `ssh_host_key_algorithm`,
   `ssh_host_key_public_key`, `ssh_host_key_fingerprint_sha256`, `ssh_host_key_trusted_at`, and
   `ssh_host_key_trusted_by` to `load_nodes`, constrains `ssh_host_key_trusted_by` to `users.id`,
   and resets every non-archived, non-disabled node to `uninitialized` with
   `LOAD_NODE_SSH_HOST_KEY_UNTRUSTED`.
2. `0020_p0_runtime_version.py` adds nullable `runtime_version` to `load_nodes` and
   `load_node_initialization_attempts`.
3. `0021_p0_run_allocation_runtime.py` adds nullable `expected_runtime_version` to
   `run_node_allocations` and refuses to upgrade while any Run is `initializing`, `running`, or
   `stopping`.

The matching mapped columns are in `apps/api/app/models/load_nodes.py` (the `ssh_host_key_*`
fields plus `runtime_version` on both the node and the initialization attempt) and
`apps/api/app/models/runs.py` (`expected_runtime_version` on the allocation). Runtime identity
semantics stay `ADR-0007` consistent: local `dev-<manifestHash>` and fixed versions keep their
meaning, a node records the Runtime version it actually activated, and a Run allocation carries
and enforces the expected version. A missing or mismatched expected version fails closed with
`RUNNER_RUNTIME_MISMATCH`.

Focused coverage is `apps/api/tests/test_p0_04_runtime_identity_migration.py` for the
active-Run refusal and the untouched legacy allocation, and `apps/api/tests/test_p0_07_migrations.py`
for the SQLite upgrade path, together with the Load Node initialization, allocation, Runner
protocol, and release verification suites recorded in the P2-05 Slice. Verification uses the
focused `uv run --all-packages pytest` selections, `make generate-contracts`, `make verify`,
`make verify-runtime-compat`, `make verify-p2-05-release-stack`, and `make verify-e2e`.

Remaining risks: native Linux amd64/arm64 Runtime compatibility, the digest-pinned release-stack
smoke, and the real SSH two-node flows need native runners, Docker networking, and real nodes, so
they remain outside default `make verify`; the first real `vX.Y.Z` release still owns the public
Runtime download, semantic create-only conflict handling, and Draft-to-final Release ordering;
Runtime version switching and rollback remain external deployment behavior; and the
`0021` column is nullable for legacy terminal allocations, so a callback without a matching
persisted expected version fails closed with `RUNNER_RUNTIME_MISMATCH`. The reconstruction
publishes as `latentrun/SurgePilot` on `main` with `ghcr.io/latentrun/*` images, so frozen
previous-owner, GHCR, and non-`main` branch references are deliberately rewritten.
