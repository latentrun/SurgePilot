# ADR-0005: Exclude API Catalog, Monitoring, and Scheduling Initially

- Status: Accepted

The initial milestone is limited to the manual Scenario -> Test Plan -> Run -> Run Report loop. API Catalog and import/generation flows, Monitoring integrations, and scheduled Runs are useful extensions but are not needed to prove that loop and would add unrelated UI, data, and infrastructure. They must not appear as hidden endpoints, routes, migrations, placeholder pages, disabled services, or dependencies until a later accepted decision and Slice activate them.
