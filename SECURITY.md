# Security Policy

## Report a vulnerability privately

Do not disclose a suspected vulnerability in a public issue, discussion, pull request, or social
post. Use [GitHub private vulnerability reporting](https://github.com/latentrun/SurgePilot/security/advisories/new)
and include:

- the affected release or source identifier;
- the component and configuration involved;
- reproducible steps or a minimal proof of concept;
- expected and observed impact; and
- any suggested mitigation, if available.

Remove production credentials, personal data, and unrelated secrets from the report. If GitHub
private vulnerability reporting is temporarily unavailable during repository migration, wait for
the public repository's Security tab rather than opening a public report.

## What to expect

Maintainers will assess reports in good faith, coordinate follow-up through the private advisory,
and publish remediation information when it is safe to do so. This volunteer project does not
promise a response-time SLA, bounty, embargo duration, or a fix for every report.

## Supported versions

Until the first public Release exists, no version is declared supported. After launch, security
fixes target the latest tagged Release unless its release notes state otherwise. Source snapshots and modified deployments are not separate supported versions.

## Deployment responsibility

SurgePilot is self-hosted. Operators are responsible for access controls, network exposure,
credential handling, backups, supported dependencies, and authorization to load-test target
systems. Follow the repository's documented secure bootstrap rather than publishing example
credentials or bypassing its fail-closed checks.
