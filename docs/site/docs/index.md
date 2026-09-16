---
layout: home

hero:
  name: SurgePilot Docs
  text: AI-Driven Distributed API Load Testing
  tagline: Original baseline produced by AI agents. Design reusable request flows, run distributed load tests across your nodes, and inspect real-time metrics with zero engine friction.
  image:
    src: /surgepilot-hero.webp
    alt: Illustrative SurgePilot AI load-testing artwork; not a performance benchmark
  actions:
    - theme: brand
      text: Quickstart Guide
      link: /docs/quickstart
    - theme: alt
      text: Startup Modes
      link: /docs/startup-modes
    - theme: alt
      text: Terms and FAQ
      link: /docs/faq

features:
  - title: 🤖 Original AI-Authored Baseline
    details: The original baseline was produced by AI agents under human direction; the responsibility boundary and evidence map are documented for inspection.
  - title: ⚡ One-Command Bootstrap
    details: Run `surgepilot up` to interactively configure and launch the full stack — Web UI, FastAPI control plane, PostgreSQL, MinIO, Nginx, and InfluxDB/Grafana monitoring on host infrastructure in seconds.
  - title: 🧾 Auditable Engineering Evidence
    details: Governance documents, contracts, tests, and release assets keep the system inspectable from product intent through verification.
  - title: 🌐 Distributed Linux Runners
    details: Decoupled control plane and execution engines. Automate remote Linux Load Nodes over SSH/SFTP with multi-node metric aggregation and real-time InfluxDB metric streaming.
  - title: 🔒 Data & Secret Isolation
    details: Multi-team Workspace isolation, encrypted-at-rest Load Node credentials, masked Env Group secret variables, and contract-bound role permission checks.
  - title: 📊 Authoritative Verdicts & Reports
    details: Reusable request flows and load models deliver deterministic PASS/FAIL verdicts, detailed response metrics, failure breakdowns, and downloadable run artifacts.
---

## What is SurgePilot?

SurgePilot is a self-hosted platform for designing, running, and reviewing API
load tests. It separates reusable request flows from environment values and load
settings, then executes them on one or more Linux Load Nodes.

SurgePilot is intended for developers, performance engineers, and internal
platform teams that want a controlled load-testing workflow on infrastructure
they operate.

## Core workflow

SurgePilot separates what to test from how and where to run it:

- **Scenario** — define reusable API and business request flows.
- **Env Group** — supply environment-specific values without changing the flow.
- **Test Plan** — combine a Scenario with load settings, execution resources, and pass/fail criteria.
- **Load Node** — provide the Linux host that executes the test.
- **Run Report** — review the verdict, metrics, diagnostics, and artifacts.

## 🔄 The Shortest Path

1. Follow the [Quickstart](./quickstart.md) to start the complete stack with `surgepilot up`.
2. Use [First Run](./first-run.md) to create an environment, a Scenario, and a Test Plan.
3. Attach a [Load Node](./first-run.md#prepare-a-load-node) and execute your first controlled Run.
4. Open [Terms and FAQ](./faq.md) when a product term or startup boundary is unclear.

::: warning Test only systems you are authorized to test
Even a small load test sends real traffic. Start with low concurrency and a
short duration against a non-production target that you own or have explicit
permission to test.
:::
