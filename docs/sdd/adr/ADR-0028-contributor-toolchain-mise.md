# ADR-0028: Repository-managed Contributor Toolchain

- Status: Accepted
- Approved: 2026-09-21
- Scope: Repository-wide source-contributor host toolchain selection, bootstrap, isolation, execution, CI alignment, and drift verification
- Related issue: [#35 Add a mise-managed contributor toolchain bootstrap](https://github.com/latentrun/SurgePilot/issues/35)
- Baseline reviewed: `origin/main` at `772f44577746e18e4745489bd2a63466f3fd3410`

## Context

SurgePilot currently declares compatible host-runtime policy in several ecosystem-specific files,
including `.python-version`, `.nvmrc`, Python package constraints, Ruff configuration, and the root
`packageManager` field. Contributors must still prepare Python, Node.js, pnpm, and uv themselves,
which allows local setup to drift from CI and encourages machine-global runtime changes.

Issue #35 requires one official project-level workflow through which a human or AI contributor can
clone the repository and run the existing Make entry points with repository-selected tools. The
workflow must preserve the existing dependency authorities:

- Make remains the contributor-facing command surface.
- uv remains the Python dependency and project-environment authority.
- pnpm remains the Node dependency authority.
- Python dependencies remain in the repository `.venv`.
- Node dependencies remain project-local.

The design must also preserve these existing boundaries:

- tagged releases own `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`;
- source deployment state under `.surgepilot` is private runtime/deployment state, not toolchain
  state;
- host Java and Go are not part of the approved contributor toolchain;
- source startup and verification continue to use the existing `make ...` commands;
- CI must not install one toolchain with setup actions and then silently download a second one;
- multiple task worktrees may operate concurrently on the same machine.

## Options Considered

### Option A: Keep host tools entirely user-managed

Rejected. This preserves setup drift, makes CI alignment advisory rather than executable, and does
not satisfy Issue #35's fresh-clone bootstrap requirement.

### Option B: Require contributors to install and activate mise themselves

Rejected. It exposes a second contributor command surface, depends on an uncontrolled system mise
version, and makes shell activation and user mise configuration part of repository behavior.

### Option C: Put a managed toolchain inside `.surgepilot`

Rejected. `.surgepilot` is private deployment state with separate ownership, permission, cleanup,
and lifecycle requirements. Development tools must not share that boundary.

### Option D: Put contributor tools below the tagged-release installation root

Rejected. `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot` is wholly owned by the user-local
release installer. Creating a contributor child there can block a later release install or modify
an installed release payload.

### Option E: Use a pinned, isolated mise bootstrap behind Make

Selected. The repository owns the mise version,
artifacts, tool policy, isolation, validation, and Make integration while keeping mise invisible in
the normal contributor workflow.

### Option F: Move all source development into a container or introduce Nix/devcontainers

Rejected. This is unnecessary for the approved requirement and would add a parallel development
environment, new lifecycle work, and broader changes to source startup.

## Decision

### Contributor-facing contract

Human and AI contributors continue to use:

```bash
make setup
make start-full-stack
make generate-contracts
make verify
```

They do not need to install, activate, or understand mise. The execution model is:

```text
Human / AI
    |
    v
make <goals>
    |
    v
classify complete MAKECMDGOALS
    |
    +-- toolchain-free -----------> execute directly
    |
    +-- management target --------> install/check directly
    |
    +-- toolchain-required
             |
             v
       managed or external mode
             |
             v
        one Make re-entry
             |
             v
         real recipes
```

Make is the repository task authority. mise is an internal host-tool selector and installer, not a
replacement task runner.

### Managed tools and version policy

The root `mise.toml` declares:

```toml
[tools]
python = "3.12"
node = "22"
pnpm = "11.3.0"
uv = "0.12.17"
```

| Tool | Policy |
| --- | --- |
| Python | `3.12.x` series |
| Node.js | `22.x` series |
| pnpm | exactly `11.3.0` |
| uv | exactly `0.12.17` |

These ecosystem compatibility declarations remain:

```text
.python-version                  3.12
.nvmrc                           22
package.json packageManager      pnpm@11.3.0
API requires-python              >=3.12
Runner requires-python           >=3.12
Ruff target                      py312
```

They are verified projections of repository policy, not additional competing authorities.
`.python-version` and `.nvmrc` are not inputs to the official managed mise resolution path.

ADR-0028 guarantees repository/CI version-policy alignment. It does not guarantee byte-identical
Python and Node artifacts across arbitrary future dates because `3.12` and `22` remain series
selectors. pnpm, uv, and the mise bootstrap are exact pins. `mise.lock` is not introduced.

### Pinned mise bootstrap and integrity authority

The repository bootstrap uses mise `v2026.9.11` and never downloads a `latest` URL. It does not use
or modify a system-installed mise.

The immutable artifact mapping is:

| Host tuple | Artifact | SHA-256 |
| --- | --- | --- |
| glibc Linux x86_64 | `mise-v2026.9.11-linux-x64.tar.gz` | `02a19e4a5eda23cda916503ad09dbc608a249fe7a7d5686c5a74ff3a7ce3b7e0` |
| glibc Linux aarch64 | `mise-v2026.9.11-linux-arm64.tar.gz` | `d781ce1b4daad6ead469b0a57fef4bfb49c4e02025dc88111ff1bfaa8c90aad9` |
| macOS x86_64 | `mise-v2026.9.11-macos-x64.tar.gz` | `46a67b050d53f1ee795353f8ff5ecfd79328a1f6415f4b3ede79ecda7223f969` |
| macOS arm64 | `mise-v2026.9.11-macos-arm64.tar.gz` | `34e8296f932c1d6f3b84d924bbb9f2841336d7bee1c373005d479e13664cb6c0` |

Every artifact URL is:

```text
https://github.com/jdx/mise/releases/download/v2026.9.11/<artifact>
```

The implementation stores this exact mapping in `scripts/toolchain-mise.sha256`. That file is the
executable integrity authority. Governance tests require it to match this accepted mapping so that
the ADR and executable source cannot drift.

A future mise update must change the version, artifact mapping, tests, and fresh-bootstrap evidence
in one explicitly reviewed change.

### Supported hosts and prerequisites

Managed bootstrap supports only:

```text
macOS x86_64
macOS arm64
glibc Linux x86_64
glibc Linux aarch64
```

Alpine/musl Linux, native Windows, and other architectures are not supported. A musl or otherwise
unsupported host fails with a clear error and never falls back to an incompatible artifact.

Source contributors still require:

```text
POSIX shell
Git
GNU or compatible Make
curl
tar/gzip
SHA-256 verification utility
```

Full source startup additionally requires Docker and Docker Compose v2. Contributors do not need
to pre-install mise, Python, Node.js, pnpm, or uv.

### Contributor storage namespace and original XDG capture

Contributor toolchain state uses a sibling namespace that cannot collide with tagged releases:

```text
${ORIGINAL_XDG_DATA_HOME:-$HOME/.local/share}/surgepilot-contributor-toolchain/
${ORIGINAL_XDG_CACHE_HOME:-$HOME/.cache}/surgepilot-contributor-toolchain/
${ORIGINAL_XDG_STATE_HOME:-$HOME/.local/state}/surgepilot-contributor-toolchain/
${ORIGINAL_XDG_CONFIG_HOME:-$HOME/.config}/surgepilot-contributor-toolchain/
```

The root Makefile captures the original process XDG values with immediate evaluation before its
existing temporary `XDG_DATA_HOME=/tmp/surgepilot-xdg-data` default is applied. It derives and
exports dedicated variables:

```text
SURGEPILOT_TOOLCHAIN_DATA_ROOT
SURGEPILOT_TOOLCHAIN_CACHE_ROOT
SURGEPILOT_TOOLCHAIN_STATE_ROOT
SURGEPILOT_TOOLCHAIN_CONFIG_ROOT
```

Explicit user-provided absolute `SURGEPILOT_TOOLCHAIN_*` roots take precedence. `scripts/toolchain`
uses only those dedicated variables and never derives persistent contributor state from the
post-Make `XDG_*` environment.

The tagged-release path remains independently owned:

```text
~/.local/share/
├── surgepilot/                       # tagged release
└── surgepilot-contributor-toolchain/ # source contributor tools
```

### Filesystem safety

Every configured contributor-toolchain root must be:

- absolute;
- a directory owned by the current user;
- not a symlink;
- not group- or other-writable.

Directories created by SurgePilot are owner-only. Components created below a toolchain root, and
any parent created by the bootstrap, reject symlink substitution and wrong ownership. Existing
normal system ancestors such as `/`, `$HOME`, and `$HOME/.local` are not required to be mode
`0700`. The bootstrap never silently takes ownership of an existing foreign-owned path.

### Complete mise isolation and project discovery

Before invoking managed mise, the wrapper clears inherited `MISE_*` variables and reconstructs only
the approved environment. Ordinary proxy variables such as `HTTP_PROXY`, `HTTPS_PROXY`, and
`NO_PROXY` may pass through.

Every managed invocation supplies isolated values beneath the contributor roots for:

```text
MISE_DATA_DIR
MISE_CACHE_DIR
MISE_STATE_DIR
MISE_CONFIG_DIR
MISE_SYSTEM_DATA_DIR
MISE_GLOBAL_CONFIG_FILE
MISE_SYSTEM_CONFIG_DIR
MISE_SYSTEM_CONFIG_FILE
```

`MISE_SYSTEM_DATA_DIR` is mapped to an isolated contributor-owned location such as:

```text
<toolchain-data>/mise-system
```

Repository-managed mise must not discover or execute tools from the host's default system-wide
mise installation directory, including `/usr/local/share/mise/installs`. The isolated system data
directory is part of executable-provenance validation.

Project discovery is fixed by all of the following requirements:

1. the invocation working directory is the canonical repository root;
2. `MISE_CEILING_PATHS` is the canonical repository root's parent, so the root config is included
   and parent configs are excluded;
3. `MISE_OVERRIDE_CONFIG_FILENAMES=mise.toml` excludes default local and environment-specific mise
   filenames;
4. `MISE_OVERRIDE_TOOL_VERSIONS_FILENAMES=none` disables `.tool-versions` input;
5. `MISE_AUTO_ENV=false` disables automatic platform-environment config discovery;
6. `MISE_IDIOMATIC_VERSION_FILE_ENABLE_TOOLS=` keeps idiomatic version-file discovery disabled;
7. `.python-version` and `.nvmrc` remain drift-checked compatibility files and are not mise inputs;
8. `MISE_LOCKFILE=false` disables all mise lockfile reads, creation, and updates;
9. `MISE_ENABLE_TOOLS=python,node,pnpm,uv` is the complete effective-tool allowlist.

User global config, system config, parent config, `mise.local.toml`, `mise.<env>.toml`,
`.tool-versions`, and idiomatic version files cannot alter the official managed tool selection.

While ADR-0028 retains series selectors for Python and Node.js, no `mise.lock` or variant lockfile
may change those selectors into implicit patch or artifact pins. Governance tests verify both the
effective `MISE_LOCKFILE=false` setting and the absence of a tracked root-level `mise*.lock` file.

`make toolchain-check` verifies the effective config sources, exact tool allowlist, versions, and
resolved executable provenance rather than validating only the text of `mise.toml`.

### uv Python ownership

mise owns contributor Python selection. uv owns project dependencies and `.venv`, but must not
create a second Python lifecycle.

Repository-managed execution sets:

```text
UV_PYTHON_DOWNLOADS=never
UV_NO_MANAGED_PYTHON=1
```

If mise-selected Python is unavailable, execution fails. uv cannot repair that failure by
downloading or selecting a uv-managed interpreter.

### Mutation, validation, and execution phases

mise automatic installation is not permitted outside the serialized mutation phase.

| Phase | Network | Toolchain mutation | Required mise behavior |
| --- | --- | --- | --- |
| bootstrap/install/repair | allowed | allowed under the mutation lock | explicit `mise install`; no implicit parallel installation |
| `toolchain-check` | forbidden | forbidden | offline, auto-install disabled, system fallback disabled |
| normal Make execution after ensure | Make recipe dependent | no mise tool installation | auto-install disabled, system fallback disabled |
| external CI validation/execution | workflow dependent | no managed installation | no mise bootstrap or fallback |

After explicit installation succeeds and before the lock is released, the wrapper validates:

- all four requested tools are installed in the contributor-owned managed data root;
- actual versions satisfy repository policy;
- effective config sources are approved;
- each executable resolves from the isolated managed toolchain rather than system PATH or the
  host's default system-wide mise installation directory.

Implicit mise installation is disabled in every phase. The install/repair phase invokes explicit
`mise install` while holding the mutation lock. Check and normal execution set:

```text
MISE_AUTO_INSTALL=0
MISE_EXEC_AUTO_INSTALL=0
MISE_NOT_FOUND_AUTO_INSTALL=0
MISE_TASK_RUN_AUTO_INSTALL=0
MISE_NOT_FOUND_SYSTEM_FALLBACK=0
```

Missing or invalid tools fail and direct the contributor to `make toolchain-install`; they never
install after the mutation lock has been released.

### Shared-state concurrency and immutable layout

Multiple branches and worktrees share contributor toolchain state. All managed mutations use one
single-writer convergence contract.

The pinned bootstrap uses an immutable versioned path:

```text
<toolchain-data>/
└── bootstrap/
    └── mise/
        └── v2026.9.11/
            └── <platform>/
                └── mise
```

Required behavior:

1. downloads and extraction use process-unique staging paths;
2. staging and publication are on the same filesystem when atomic rename is required;
3. SHA-256 is verified before publication;
4. unverified or partial content is never executable from the final path;
5. final publication is atomic;
6. concurrent first bootstrap converges to one valid final artifact;
7. all tool install and repair mutations are serialized;
8. a waiter re-checks valid state after acquiring the lock;
9. an interrupted process cleans only its own staging state;
10. one process never deletes another process's staging or published result;
11. an existing valid pinned version survives another process's failure;
12. a later pinned version is published separately and cannot destroy the previous version;
13. a stale or interrupted mutation is recoverable by a later invocation.

The implementation may use a portable lock directory, a file lock, or an equivalent mechanism as
long as these observable semantics hold on macOS and supported Linux hosts.

Normal command execution does not retain the mutation lock and cannot trigger mise auto-install.

### Make target classification

The complete `MAKECMDGOALS` is classified before recipes execute.

Toolchain-free goals include at minimum:

```text
help
dev
infra-up
infra-down
e2e-clean
stop-preview
stop-full-stack
stop-full-ssh-e2e
```

These execute without mise, network bootstrap, or Make re-entry. Recovery targets remain usable
when toolchain state is absent or corrupt. They may still fail if their own host prerequisite, such
as Docker, is unavailable.

Toolchain-management goals are:

```text
toolchain-install
toolchain-check
```

Each management goal must be the only requested goal. A command that mixes either management goal
with any other goal fails before executing any recipe. This includes mixing the two management
goals with each other.

All remaining public goals default to toolchain-required unless explicitly classified otherwise.
This makes new targets safe by default.

An invocation with empty `MAKECMDGOALS` resolves to the existing default `help` behavior and never
bootstraps the toolchain.

Multi-goal behavior is:

- all goals toolchain-free: execute directly with no re-entry;
- any goal toolchain-required: ensure once, then re-enter once with the complete original goal set;
- mixed free and required goals: re-enter the complete original goal set once;
- any management goal mixed with another goal: fail before executing recipes.

### Single Make re-entry

Toolchain-required top-level commands use `SURGEPILOT_TOOLCHAIN_ACTIVE=1` as an internal sentinel:

```text
make <goals>
    |
prepare and validate managed/external environment
    |
SURGEPILOT_TOOLCHAIN_ACTIVE=1
    |
$(MAKE) <same complete goals>
    |
real recipes
```

Recursive `$(MAKE)` calls inherit the sentinel and toolchain environment and do not bootstrap
again. Re-entry preserves `MAKEFLAGS`, `MAKEOVERRIDES`, `MAKECMDGOALS`, jobserver state, and
command-line variable overrides. It uses `$(MAKE)`, never a hard-coded `make` executable.

### Toolchain management commands

`make toolchain-install` is the explicit mutable installation and repair entry. It may create safe
toolchain roots, use the network, download and verify pinned mise, publish it atomically, run
explicit `mise install` under the mutation lock, repair incomplete state, and validate the result.

`make toolchain-check` is an offline, non-installing, non-repairing diagnostic. It:

- performs no network access;
- does not bootstrap mise;
- does not install or repair tools;
- does not create missing roots or directories;
- sets `MISE_OFFLINE=1`, `MISE_AUTO_INSTALL=0`, `MISE_EXEC_AUTO_INSTALL=0`,
  `MISE_NOT_FOUND_AUTO_INSTALL=0`, `MISE_TASK_RUN_AUTO_INSTALL=0`, and
  `MISE_NOT_FOUND_SYSTEM_FALLBACK=0`;
- fails with `Run: make toolchain-install` when required state is absent or invalid;
- verifies versions, config sources, tool allowlist, isolated `MISE_SYSTEM_DATA_DIR`, effective
  `MISE_LOCKFILE=false`, and executable provenance;
- leaves the managed toolchain tree unchanged.

The implementation test snapshots the relevant managed tree before and after `toolchain-check` to
prove the non-mutating contract. If the pinned mise process cannot satisfy that contract for a
specific diagnostic, the wrapper performs that validation itself rather than weakening the public
command semantics.

Normal toolchain-required goals such as `make setup`, `make verify`, and
`make start-full-stack` may automatically perform the same idempotent locked ensure used by
`toolchain-install`. Contributors do not need to run the install target first.

`make toolchain-tests` is toolchain-required and runs the focused toolchain governance and
bootstrap tests through the repository-managed environment.

### CI external mode

Existing GitHub Actions setup actions remain the CI installation path. Jobs use an explicit
externally provisioned mode, conceptually:

```text
SURGEPILOT_TOOLCHAIN_MODE=external
SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS=<comma-separated subset>
```

External mode:

1. never downloads or installs mise;
2. never installs managed tools or falls back to managed mode;
3. accepts only known, non-duplicated tool names from `python`, `uv`, `node`, and `pnpm`;
4. validates every tool declared for that job;
5. fails closed on an empty, unknown, malformed, or insufficient declaration;
6. re-enters Make once after validation.

External version policy is:

```text
Python -> 3.12 series
Node   -> 22 series
pnpm   -> exactly 11.3.0
uv     -> exactly 0.12.17
```

Every `astral-sh/setup-uv` use explicitly selects `0.12.17`. Every job that executes host
`python` or `python3` provisions Python 3.12 in that same job. Governance tests validate CI jobs
semantically rather than accepting a version configured in an unrelated job.

A dedicated managed-mode fresh-clone smoke does not obtain Python, Node.js, pnpm, or uv from the
normal setup actions. It runs:

```bash
make toolchain-install
make toolchain-check
make setup
make toolchain-tests
```

Native managed smoke runs on Linux and macOS where runners are available. Platform mapping and
checksum tests cover all four supported tuples. Required native checks that cannot run are reported
as `NOT VERIFIED`; they are not silently represented as passed.

### Documentation and governance synchronization

Implementation adds:

```text
mise.toml
scripts/toolchain
scripts/toolchain-mise.sha256
tests/contract/test_toolchain_governance.py
tests/test_toolchain_bootstrap.py
docs/sdd/adr/ADR-0028-contributor-toolchain-mise.md
```

Implementation updates:

```text
Makefile
AGENTS.md
CONTRIBUTING.md
docs/sdd/README.md
docs/sdd/adr/README.md
docs/sdd/02-repo-structure-and-dev-workflow.md
docs/site/docs/quickstart.md
docs/site/docs/zh-CN/quickstart.md
docs/site/docs/ja/quickstart.md
applicable GitHub Actions workflows
```

The existing root `AGENTS.md` mise guidance is replaced and condensed rather than duplicated. It
directs human and AI contributors to repository Make targets, prohibits manual/global runtime
selection, preserves `.venv` and project-local Node dependencies, and keeps host Java/Go outside
the contributor toolchain. Dynamic version numbers remain in `mise.toml`, not `AGENTS.md`.

All three source Quickstarts describe the same source-contributor prerequisites and automatic Make
bootstrap. They no longer require contributors to pre-install Python, Node.js, pnpm, uv, or mise.
Documentation tests prevent locale drift.

No product PRD or product Scope Gate change is required because this decision changes repository
contributor workflow, not product behavior.

## Consequences

### Positive

- A fresh source checkout has one official contributor command surface: Make.
- Repository-selected host tools do not change machine-global runtime defaults.
- User and system mise configuration cannot alter the supported workflow.
- Contributor tools, deployment state, and tagged-release installation remain independent.
- Multiple worktrees share downloads without permitting concurrent partial publication.
- Recovery and teardown commands remain usable when the toolchain or network is unavailable.
- CI can retain efficient setup actions while proving policy alignment per job.
- Drift between repository declarations, CI, docs, and actual effective tools becomes testable.

### Costs and tradeoffs

- First managed use downloads a pinned mise binary and the selected tool runtimes.
- The repository owns bootstrap integrity data, locking, platform detection, and update evidence.
- Shared tool state requires explicit stale-lock and interrupted-install recovery behavior.
- Python and Node patch versions may move within their approved series over time.
- CI has two provisioning paths—managed smoke and external setup—but one version policy and one Make
  execution contract.
- glibc-only Linux support excludes Alpine/musl contributors unless a later approved decision adds
  the separate artifacts and acceptance coverage.

## Non-goals

ADR-0028 does not introduce:

```text
mise tasks
mise.lock
asdf compatibility
Nix
devcontainer
Corepack bootstrap
global Python, Node.js, or pnpm installation
shell activation or shell-rc mutation
sudo or a Homebrew requirement
host Java or Go
musl/Alpine support
native Windows support
release-installer changes
Load Node Runtime changes
production runtime changes
product VERSION changes
```

## Acceptance Criteria

Implementation is complete only when:

- [ ] `mise.toml` selects Python 3.12, Node 22, pnpm 11.3.0, and uv 0.12.17.
- [ ] the pinned mise artifact manifest exactly matches this ADR.
- [ ] contributor state cannot collide with `.surgepilot` or the tagged-release install root.
- [ ] roots derive from original XDG/HOME state, not Make's temporary XDG override.
- [ ] filesystem ownership, symlink, absolute-path, and permission checks fail closed.
- [ ] managed config discovery loads only the root `mise.toml` and isolated empty global/system
  config sources.
- [ ] effective managed tools are exactly Python, Node.js, pnpm, and uv.
- [ ] resolved executables come from the isolated managed root rather than system PATH.
- [ ] `MISE_SYSTEM_DATA_DIR` is isolated and managed mise cannot discover or execute tools from the
  host's default system-wide mise installation directory.
- [ ] `MISE_LOCKFILE=false` is effective, no tracked root-level `mise*.lock` exists, and lockfiles
  cannot alter the approved Python/Node series-version policy.
- [ ] uv cannot download or select a uv-managed Python.
- [ ] all mise installation and repair occurs under the single-writer mutation lock.
- [ ] check and normal execution cannot trigger mise auto-install or system fallback.
- [ ] concurrent first bootstrap converges to one valid immutable artifact.
- [ ] interrupted bootstrap recovers without damaging valid state.
- [ ] toolchain-free stop/cleanup targets work without bootstrap or network.
- [ ] an empty-goal `make` remains lightweight help.
- [ ] management goals mixed with any other goal fail before recipes execute.
- [ ] required multi-goal commands re-enter exactly once with all original goals.
- [ ] command-line Make variables and jobserver semantics survive re-entry.
- [ ] `toolchain-check` is offline, non-installing, non-repairing, and leaves managed state unchanged.
- [ ] normal managed goals automatically ensure the toolchain.
- [ ] CI external mode never performs a second managed installation.
- [ ] CI validates versions and required tool subsets per job.
- [ ] managed fresh-clone smoke reaches dependency setup and focused repository verification.
- [ ] all four platform mappings and checksums have automated coverage.
- [ ] unavailable required native checks are reported as `NOT VERIFIED`.
- [ ] `.venv` and Node dependencies remain project-local.
- [ ] no host Java or Go is introduced.
- [ ] English, Chinese, and Japanese source Quickstarts remain semantically aligned.
- [ ] affected governance, workflow, and documentation sources agree with implementation.
- [ ] `make verify` passes.
- [ ] product, runtime, release behavior, and product `VERSION` remain unchanged.

Focused tests include at minimum:

```text
platform and libc mapping
artifact URL and SHA-256 validation
corrupt-download rejection
unsupported-host rejection
filesystem ownership/permission/symlink rejection
config-source isolation
tool allowlist and executable provenance
system-wide mise install discovery rejection
lockfile disablement and tracked-root-lockfile rejection
uv Python restrictions
concurrent first bootstrap
interrupted bootstrap recovery
toolchain-check non-mutation
empty-goal and management-goal rejection
toolchain-free multi-goal execution
required and mixed multi-goal single re-entry
recursive Make without a second bootstrap
command-line variable and jobserver preservation
managed and external mode validation
CI and ecosystem declaration drift
three-locale documentation drift
```

## Related ADRs

- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md` — separates source contributor
  bootstrap from tagged-release distribution and Runtime artifacts.
- `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md` — owns the existing source preview entry
  whose Make behavior must remain available.
- `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md` — owns the independent
  `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot` release namespace.

## References

- `AGENTS.md`
- `Makefile`
- `CONTRIBUTING.md`
- `infra/release/install.sh`
- `docs/sdd/README.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `docs/sdd/adr/README.md`
- `docs/site/docs/quickstart.md`
- `docs/site/docs/zh-CN/quickstart.md`
- `docs/site/docs/ja/quickstart.md`
- [mise v2026.9.11 release](https://github.com/jdx/mise/releases/tag/v2026.9.11)
- [mise configuration settings](https://mise.jdx.dev/configuration/settings.html)
- [mise system-wide tool installs](https://mise.jdx.dev/dev-tools/)
- [mise lockfiles](https://mise.jdx.dev/dev-tools/mise-lock.html)
- [uv Python version management](https://docs.astral.sh/uv/concepts/python-versions/)


