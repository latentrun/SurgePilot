# ADR-0001: Use a Monorepo

- Status: Accepted

SurgePilot keeps Web, API, Runner, contracts, migrations, infrastructure, tests, and documentation in one repository so a contract change and all of its consumers can be reviewed and verified together. Separate repositories would add coordination and release overhead before the initial product needs independent release cadence. Monorepo location does not weaken boundaries: Web consumes generated contracts, Runner does not import API internals, and repository checks guard generated-artifact freshness and cross-application imports.
