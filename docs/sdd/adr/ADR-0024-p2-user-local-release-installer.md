# ADR-0024: P2 User-local Release Installer

- Status: Accepted
- Scope: Tagged platform Release installation only
- Active Slices: `docs/sdd/slices/P2-05-cross-platform-distribution.md` and
  `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Partial supersession: Platform-installer exclusions in ADR-0017 and ADR-0018 only; the
  existing-installation rule is superseded by ADR-0029
- Related ADRs: ADR-0017, ADR-0018, ADR-0020, ADR-0021, and ADR-0029

## Context

The tagged Release already contains the complete digest-pinned Compose deployment, secure
bootstrap helpers, lifecycle wrapper, and architecture-specific Runtime references. The current
user path still requires manual archive download, checksum handling, extraction, directory
navigation, and `./surgepilot up`. Those archive mechanics do not represent an operator decision
and make the first use less convenient than the release wrapper itself.

The repository has not published a semantic Release, so the first supported installation layout
does not require migration or compatibility behavior. The implementation should establish a small
public contract without becoming an installer framework, package manager, updater, or privileged
host bootstrap.

The installation command cannot safely start the platform inside the same pipeline. Standard input
belongs to the downloaded shell script, while P2-06 requires a real interactive terminal for the
first `up` host/port review. Installation and startup must therefore remain two commands.

## Options Considered

### Option A: Version-pinned user-local installer plus separate `surgepilot up`

Accepted. A POSIX `install.sh` released with each semantic version downloads and verifies that
exact version's bundle, publishes it below the user's home directory, creates a user-owned command
launcher, and exits. The existing release wrapper continues to own every deployment decision.

### Option B: Keep manual archive extraction as the only path

Rejected as the ordinary path. It remains a useful advanced/private fallback, but it exposes
release transport details that one bounded installer can remove without changing deployment
semantics.

### Option C: Install and start through one `curl | sh` pipeline

Rejected. It conflicts with first-run TTY requirements, combines two failure domains, and makes a
network-delivered script create deployment state and start containers without a separate operator
step.

### Option D: Publish through package managers or system locations

Rejected. Homebrew, apt, yum, desktop packages, `/opt`, `/usr/local`, `sudo`, and Docker
installation add release, privilege, platform, and support surfaces that are unnecessary for the
two-command experience.

## Decision

1. Every semantic platform Release publishes:
   - `install.sh`;
   - `surgepilot-vX.Y.Z.tar.gz`;
   - `surgepilot-vX.Y.Z.tar.gz.sha256`;
   - the already-governed versioned Linux Runtime archives, sidecars, and manifests.
2. `install.sh` is POSIX `sh`, has the exact semantic version rendered into it, and downloads the
   versioned bundle and sidecar from `/releases/download/vX.Y.Z/`. It does not resolve the bundle
   through `latest`, so a concurrent Release cannot mix installer and payload versions.
3. The public ordinary flow is:

   ```sh
   curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
   surgepilot up
   ```

   A `surgepilot.dev/install.sh` alias may redirect to the same GitHub installer asset only after
   that redirect exists. Documentation must not present the alias as working before then.
4. The default deployment root is
   `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`. The installer publishes the bounded release
   files there. The existing wrapper later creates `.env` and `.surgepilot` in the same stable
   deployment root.
5. The installer creates `$HOME/.local/bin/surgepilot` as a small launcher that executes the
   installed wrapper by its absolute installation path. It is not a symlink because the wrapper
   resolves release files relative to `$0`.
6. The launcher may set `SURGEPILOT_COMMAND_NAME=surgepilot` for display text only. The manually
   extracted wrapper defaults to `./surgepilot`. This variable never changes Compose, Runtime,
   credentials, secrets, or persisted configuration.
7. The installer requires only base POSIX utilities, `curl`, `tar`, and `sha256sum` on Linux or
   `shasum -a 256` on macOS. It does not require Python, Node.js, `jq`, GitHub CLI, Docker, or a
   language toolchain. Docker Engine/Desktop and Compose remain `surgepilot up` prerequisites.
8. The installer uses `umask 077`, downloads into private temporary state, validates the exact
   lowercase SHA-256 before extraction, rejects unexpected or non-regular archive members,
   requires the exact standalone version marker plus canonical top-level manifest version, and
   publishes through same-parent temporary paths plus `mv`.
9. For releases before ADR-0029, an existing deployment root or launcher fails closed. ADR-0029
   supersedes that blanket rule only for its exact installed-release transition; operator-owned
   `.env`, private state, volumes, and the launcher remain preserved. A fresh launcher-publication
   failure may remove only the new deployment root that the same run proved absent and just
   published. Catchable termination signals cannot interrupt the bounded two-path publication
   window and leave only one destination published.
10. The installer never invokes `sudo`, changes groups, installs or configures Docker, writes shell
    startup files, changes `PATH`, or calls `surgepilot up`. When `$HOME/.local/bin` is not in
    `PATH`, it prints the direct command and a copyable export instruction.
11. The production installer owns only public GitHub Release downloads. Private-repository
    validation uses `GITHUB_TOKEN` and an external test harness to retrieve the unchanged assets,
    then serves the same bytes through a loopback fixture. Private GitHub API parsing, `jq`, and
    GitHub CLI do not enter the production installer.
12. Existing validation and semantic workflows validate the sidecar, run installer-only smoke on
    Linux and macOS, and start native release-stack smoke from an installed deployment rather than
    direct archive extraction. Native Runtime/image, Demo Debug Run, Monitoring, anonymous GHCR,
    and create-only publication gates remain unchanged.
13. Manual download, sidecar verification, extraction, and `./surgepilot up` remain an advanced
    fallback. They are not the primary Quick Start after this ADR is implemented.
14. Source `make start-full-stack` / `make start-preview`, release `up` configuration, Runtime
    selection and fetch, immutable image digests, secrets, Workspace, Runner protocol, and Public
    API AI skill distribution do not change.

## Failure Ordering

The installer validates its host and tools, destination absence, downloads, checksum, extracted
payload, and manifest version before publishing either destination. Ordinary failures and signals
remove temporary state. Failures before publication leave the deployment root and launcher absent.
If the deployment root is published and final launcher publication then fails, the installer
removes only that newly published root and returns non-zero.

The installer prints no token, signed asset URL, credential, secret, `.env` content, or archive
content. `surgepilot up` retains its existing fail-closed Docker, manifest, terminal,
configuration, Runtime, Compose, and health ordering after installation succeeds.

## Supersession Boundary

This ADR supersedes only statements in ADR-0017, ADR-0018, P2-05, and P2-06 that forbid any
platform Release installer, downloader, `curl | sh` entry, installer asset, installer validation
job, or bundle checksum. It authorizes exactly the bounded user-local installer described here.

It does not supersede exclusions for package managers, system installers, privileged host
changes, Docker installation, automatic update/rollback/uninstall, signing, SBOM publication,
new registries, public workflow dispatch, or standalone Public API AI skill publication and
installation.

## Consequences

1. A fresh user removes manual download, checksum, extraction, and directory-navigation steps
   while retaining an explicit second command for deployment.
2. Linux and macOS share one host script and one command location without claiming native macOS
   Load Node or Runtime support.
3. The stable deployment root keeps release files and deployment state together. Automatic
   version transitions remain outside this ADR.
4. The Release adds one small script, one checksum sidecar, workflow smoke, and focused tests; it
   does not add a service, API, database change, installer daemon, or package ecosystem.

## References

- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
