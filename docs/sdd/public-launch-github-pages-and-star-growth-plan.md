# Public Launch, GitHub Pages, SEO, and Star-Growth Plan

- Status: Proposed for review; this document does not activate implementation
- Target repository: `latentrun/SurgePilot`
- Planned public site: `https://latentrun.github.io/SurgePilot/`
- Planned documentation root: `https://latentrun.github.io/SurgePilot/docs/`
- Primary outcome: legitimate GitHub Star growth and increased SurgePilot and LatentRun project awareness
- Public launch shape: repository, Pages site, multilingual documentation, and an installable release launch together

## 1. Purpose

This plan separates preparation while the repository is private from actions that require explicit owner approval. It is the source for launch governance, design, implementation, release-readiness, and publication planning. It does not authorize public activation.

## 2. Strategic decision

SurgePilot is presented as a real distributed system built end-to-end by AI agents under human direction. The working self-hosted load-testing platform is the proof: independent Linux Runners, multi-node execution, state-machine safety, security boundaries, API contracts, tests, release packaging, and verification gates make the claim inspectable.

The public story has three layers:

1. Attention: the original public baseline was built by AI agents.
2. Proof: the result is a runnable, inspectable distributed system.
3. Reason to Star: the repository is useful to people studying agentic software engineering.

Product adoption, registrations, commercial leads, fabricated performance, and unsupported social proof are not launch criteria.

## 3. Authorship boundary

The public statement must define roles precisely:

> **Human role:** define product intent, discuss requirements, use the product, provide feedback, and decide whether the result is acceptable.
>
> **AI-agent role:** design the product and engineering process; author the PRD, SDDs, ADRs, slices, architecture, contracts, implementation, and tests; define and enforce quality gates; resolve verification failures; and produce deployment and release assets.

The project must not claim that no human participated. Future community contributions may be human- or AI-authored without model, prompt, or provenance attestation.

## 4. Public site architecture

The initial public URLs are:

```text
Marketing home        https://latentrun.github.io/SurgePilot/
English docs          https://latentrun.github.io/SurgePilot/docs/
Chinese docs          https://latentrun.github.io/SurgePilot/docs/zh-CN/
Japanese docs         https://latentrun.github.io/SurgePilot/docs/ja/
Repository            https://github.com/latentrun/SurgePilot
Releases              https://github.com/latentrun/SurgePilot/releases
```

One VitePress package owns the marketing homepage and exactly six English user-guide pages below `/docs/`, with exact `zh-CN` and `ja` mirrors. The site configuration owns the origin, project base, metadata, locale navigation, sitemap, robots output, social assets, and structured data. No browser-language redirect, custom domain, hosted service, pricing page, blog, CMS, programmatic SEO, or seventh user page is included.

The Pages homepage is a separate static implementation using the approved Marketing Landing visual language. It has no product authentication dependency or hosted-service promise. The self-hosted Web Landing remains a product entry point, keeps its product authentication actions, and is crawler-observable `noindex`.

## 5. Marketing and truthfulness

The homepage message hierarchy is:

1. the AI-built original-baseline hook;
2. the human/AI responsibility boundary;
3. why the system is a meaningful distributed-system proof;
4. repository-backed evidence;
5. product architecture and capabilities;
6. demonstration and installation paths;
7. the GitHub Star action.

The original animated dashboard, Recent Test Runs, and Distributed load mesh remain only as adjacent, explicit `UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA`. They are never evidence of measured capability, adoption, service health, topology, or repository facts.

Only real targets are interactive. The primary actions are Star on GitHub, Inspect the Evidence, Watch the Demo, Read the Docs, and View Releases. Missing Discord, hosted status, pricing, signup, and SaaS entries are omitted.

## 6. Launch gates

Private preparation may build and validate the static artifact, metadata, documentation, authorship evidence, demo assets, repository metadata, and launch runbook. Public activation remains gated on:

1. privacy, security, credential, and license review;
2. deliberate migration to `latentrun/SurgePilot` and matching `ghcr.io/latentrun` namespaces;
3. verification of the reviewed launch candidate;
4. immutable baseline and installable release readiness;
5. anonymous repository, image, bundle, installer, Pages, and documentation access;
6. explicit owner approval for visibility, release publication, metadata, and Pages deployment.

The launch consumes existing release and startup contracts. It does not change Runtime, installer, Compose, application publication, API, database, Runner, or Load Node behavior.

## 7. SEO, localization, and assets

Every indexable Pages route needs a unique title and description, self-canonical URL, Open Graph and Twitter metadata, one primary heading, language metadata, descriptive image alternatives, reciprocal locale alternates with `x-default`, and a stable lowercase URL under the project base. The build emits only canonical indexable routes in its sitemap and a Pages-compatible robots file. Structured data is limited to visible, supportable facts.

Asset budgets, optimized hero imagery, required font licenses, accessibility checks, keyboard focus, and desktop-Web-first full signature motion are reviewed before publication.

## 8. Community growth boundary

Legitimate discovery and Star conversion may use accurate technical storytelling, auditable evidence, public documentation, demo assets, repository metadata, and community distribution. Purchased Stars, fake accounts, misleading giveaways, fabricated adoption, synthetic benchmarks presented as real, and artificial growth methods are forbidden.
