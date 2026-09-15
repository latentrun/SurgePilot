# ADR-0021: P2 Release `up` Configuration Confirmation

- Status: Accepted
- Scope: Tagged-release `./surgepilot up` configuration display, confirmation, and explicit
  interactive standard-LAN network reconfiguration only
- Partial supersession: Only conflicting existing-`.env` "not prompted" and "never rewritten"
  wording in ADR-0017, ADR-0018, and ADR-0020
- Active Slice: `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Related ADRs: `ADR-0017-p2-cross-platform-distribution`,
  `ADR-0018-p2-lan-first-release-bootstrap`, `ADR-0020-p2-release-dual-runtime-default`

## Context

The tagged-release wrapper already validates release state through immutable API-image helpers and
keeps interactive prompting in the POSIX host shell. First-run startup shows normalized endpoints,
but its confirmation has no default and a negative answer exits. A valid existing `.env` is used
without displaying its effective non-secret configuration until after Runtime acquisition and
service startup. Correcting a standard-LAN host or published port therefore requires manual file
editing even though the same bounded normalization already exists for first run.

Existing governance deliberately protects operator-owned deployment state from automatic repair,
migration, secret rotation, and non-interactive mutation. The usability change must preserve that
boundary while authorizing one explicit, reviewable path for an interactive operator to replace
only the standard-LAN network assignments.

## Options Considered

### Option A: Keep the POSIX wrapper and add bounded helper operations

Accepted. The host shell owns terminal detection, display, prompting, and control flow. Immutable
API-image Python helpers continue to own parsing, classification, normalization, validation,
content-digest comparison, and private persistence through standard `os.replace`.

### Option B: Rewrite the release wrapper as a Python CLI

Rejected. It would add a host Python dependency and broaden the lifecycle surface without being
necessary for the four-field workflow.

### Option C: Edit `.env` with shell tools

Rejected. Shell `sed`/`awk` editing cannot safely own duplicate assignment detection, complete
release validation, file permissions, final reviewed-content checking, or private replacement.

### Option D: Regenerate the complete `.env`

Rejected. Full-env regeneration could discard operator comments and unknown fields or overwrite
Runtime, Demo, credential, secret, TLS, and other non-target state.

### Option E: Add a general `./surgepilot configure` command

Rejected. A separate general-purpose editor expands the command and configuration model. The
bounded No/re-enter loop within `up` satisfies the approved correction workflow.

## Decision

1. Every valid tagged-release `./surgepilot up` prints the effective bounded non-secret
   configuration before Runtime fetch, Compose validation/pull/up, or application-service changes.
   The summary includes Web/API and InfluxDB node-write endpoints, the persisted Runtime
   architecture value, and Demo enabled state.
2. Interactive startup asks `Use this configuration? [Y/n]:`. Empty input, `y`, or `yes`, matched
   case-insensitively, means Yes. Invalid answers repeat only the confirmation question. EOF fails
   without deployment-state changes.
3. On first run, No repeats host and port entry. For an existing standard direct-LAN HTTP
   configuration, No opens the same host and two-port entry loop with current values as defaults.
   The normalized proposal is displayed and must receive explicit default-Yes confirmation before
   persistence.
4. Existing `.env` may change only after interactive No, valid host/port entry, normalized review,
   and explicit Yes. An affirmative confirmation of the current configuration is read-only, a
   negative confirmation alone changes nothing, and an identical confirmed proposal does not
   replace the file.
5. The quick path may change only the four allowlisted network fields:
   - `SURGEPILOT_HTTP_PORT`;
   - `SURGEPILOT_NODE_API_BASE_URL`;
   - `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT`;
   - `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL`.
   The URLs are derived from one normalized host and their matching ports. Runtime selection, Demo
   state, cookie policy, credentials, secrets, project identity, comments, and unknown fields are
   preserved.
6. A complete valid existing `.env` in a non-TTY startup prints the same summary, never prompts or
   reads stdin, and continues read-only. Missing `.env` in non-TTY startup still fails closed.
   Existing malformed or incomplete state still fails validation; automatic and non-interactive rewriting remains forbidden.
7. A valid advanced HTTPS configuration is displayed and may be accepted read-only. Choosing No
   fails before Runtime or Compose side effects with guidance to edit `.env` explicitly; advanced
   HTTPS never enters the standard-LAN quick rewrite path.
8. The update helper requires the expected SHA-256 digest of the exact `.env` content that was
   reviewed. It validates a private, owner-owned, non-symlink regular file; revalidates current and
   proposed complete release state; rejects missing or duplicate target assignments; writes and
   fsyncs a same-directory mode-`0600` temporary file; validates the candidate bytes, mode, and
   owner; then performs a final pre-replacement SHA-256 check and uses standard `os.replace` before
   fsyncing the parent directory. Failures before `os.replace` leave the existing file intact and
   print no secret content.
9. This is not a strict compare-and-swap. Simultaneous manual same-user editing during the final
   check-to-`os.replace` syscall window is unsupported. The helper adds no lock, inode-CAS, or
   exchange, and it provides no backup or automatic rollback. After successful `os.replace`, a
   parent-directory fsync failure reports “updated but durability could not be confirmed; inspect
   `.env`” and halts before Runtime or Compose work; it does not restore the prior file.
10. ADR-0017, ADR-0018, and ADR-0020 remain authoritative except for wording that says a valid
   existing release `.env` is not prompted over or is never rewritten under any circumstance.
   This ADR partially supersedes only that conflict. Automatic repair/migration, automatic or
   non-interactive rewriting, and all existing secret/private-state preservation rules remain.
11. Source-checkout `make start-full-stack`, `make start-preview`, source Compose, root
    `.env.example`, release artifacts, Runtime format, image selection, API, database, Web, Runner
    protocol, Workspace, and permission contracts do not change.

## Failure Ordering

The release flow validates Docker, Compose, and the release manifest and pulls the immutable API
helper image before collecting input. It then validates and describes existing state or
normalizes first-run input, displays the summary, obtains any required confirmation, validates
port availability, and atomically creates first-run state or explicitly updates existing state with
the standard same-directory replacement sequence. Persisted state is
revalidated before Runtime selection and fetch, release Compose validation/pull/up, or application
service changes.

Invalid confirmation input, invalid host/port input, occupied proposed ports, EOF, unsafe file
state, duplicate target assignments, candidate-validation failure, or a SHA-256 mismatch detected
before `os.replace` leaves existing deployment state unchanged. Replacement failure also cleans the
temporary file and leaves existing state unchanged. A failure after successful replacement is not
rolled back: the explicit durability diagnostic halts before Runtime and Compose side effects.

## Consequences

1. Repeated `up` becomes transparent and the common standard-LAN host/port correction remains
   within the ordinary command.
2. Default-Yes confirmation keeps the read-only repeat path short while making operator consent
   explicit in interactive sessions.
3. The wrapper gains a bounded interaction loop and helpers gain non-secret description plus
   explicit four-field update operations.
4. LF/CRLF text preservation, exotic-separator rejection, final pre-replacement SHA-256 checking,
   candidate safety, no-op behavior, HTTPS exclusion, PTY behavior, and startup ordering require
   focused tests.
5. Existing secrets and non-network operator state retain the ADR-0017/P2-05 preservation
   boundary; this is not a general `.env` repair or editor capability.

## Scope Exclusions

This ADR does not authorize a host Python dependency, full wrapper rewrite, shell-based `.env`
editing, full-env regeneration, general configure command, TLS/proxy/certificate automation,
Runtime/Demo/cookie/credential changes, automatic repair or migration, source-startup changes,
application contracts, release-publication changes, a new deployment mode, strict CAS, backup, or
automatic rollback.

## References

- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `infra/release/surgepilot`
- `scripts/bootstrap_deployment_env.py`
- `scripts/release_preflight.py`
- `AGENTS.md`
