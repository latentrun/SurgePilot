# SurgePilot Community Launch Drafts

- Status: copy drafts only; do not publish until every linked surface is anonymous and verified
- Primary action: inspect the repository and legitimately Star it if the work is useful
- Language order: English first; localized adaptations are optional and must preserve the claim

## Distribution rules

- Do not cross-post every channel at once. Start with one technically relevant community, answer
  questions, and adapt later posts from real feedback.
- Do not invent benchmarks, adoption, users, Stars, or production status. Use only current,
  repository-verifiable facts.
- Do not ask for a Star in exchange for anything, buy promotion, use fake accounts, or coordinate
  reciprocal Stars.
- Identify yourself as the project owner when a community requires disclosure. Follow each
  community's self-promotion rules and remove a post if moderators request it.
- Link to the specific evidence readers ask about rather than repeating the headline without proof.
- Never publish before the repository, site, docs, Release, and any referenced video resolve in a
  logged-out session.

## English launch core

### One-sentence positioning

> SurgePilot is a self-hosted distributed API load-testing system whose original public baseline
> was authored end-to-end by AI agents under a precise human-direction and repository-governance
> boundary.

### Show HN

**Title**

```text
Show HN: SurgePilot – a distributed system whose original baseline was built by AI agents
```

**Body**

```text
I built SurgePilot as an experiment: can AI agents carry a real distributed system from
requirements and architecture decisions through contracts, code, tests, and release assets?

The human role was product intent, requirements discussion, product use, usage feedback, and
acceptance. AI agents produced and enforced the engineering artifacts and quality gates. The
claim is bound to an audited immutable baseline; future contributions can be human- or AI-authored.

The proof is the repository, not a chat screenshot: independent Load Node Runners, multi-node
execution, a Run state machine, generated API contracts, security boundaries, verification gates,
and an installable self-hosted stack.

Repository: https://github.com/latentrun/SurgePilot
Evidence and docs: https://latentrun.github.io/SurgePilot/

I would value skeptical feedback on the evidence boundary and what you would inspect first. If
the experiment is useful, a Star helps others discover it.
```

### Reddit

Choose one relevant subreddit only after reading its current rules; do not reuse this draft where
project links or self-promotion are prohibited.

**Title**

```text
I used AI agents to build the original baseline of a self-hosted distributed load-testing system
```

**Body**

```text
SurgePilot is both a working self-hosted API load-testing platform and a repository-backed
experiment in agentic software engineering.

The interesting part is not “AI generated a UI.” The repository includes its PRD → SDD → ADR →
Slice → contract → implementation → test → release trail, plus independent Linux Runners and
multi-node result aggregation. The human/AI responsibility boundary and the pending/selected
baseline tag are explicit rather than hidden behind “no human” wording.

Code: https://github.com/latentrun/SurgePilot
Evidence overview: https://latentrun.github.io/SurgePilot/
Docs: https://latentrun.github.io/SurgePilot/docs/

I am looking for technical criticism of the governance and evidence model. Please Star it only if
you want to follow or revisit the experiment.
```

### X / LinkedIn

```text
Can AI agents carry a real distributed system from requirements to release?

SurgePilot is a self-hosted API load-testing platform with independent Runners, multi-node
execution, contracts, state-machine safety, tests, and release assets. Its original public
baseline is bound to an explicit human/AI responsibility record—not a “no human” claim.

Inspect it: https://github.com/latentrun/SurgePilot
Evidence + docs: https://latentrun.github.io/SurgePilot/

If the repository is useful, Star it so you can find it again.
```

For X, shorten without removing the evidence link. For LinkedIn, add one personal paragraph about
why the owner ran the experiment; do not add unverified reach or performance numbers.

## Optional Chinese adaptation

Publish only after the English source and all links are final.

```text
AI Agent 能否把一个真实分布式系统从需求一路推进到发布？

SurgePilot 是一个自托管的分布式 API 负载测试平台。它的原始公开基线由 AI Agent 在明确的人类
指导边界下端到端完成，证据来自仓库中的 PRD、SDD、ADR、契约、代码、测试与发布资产，而不是
聊天截图。

仓库：https://github.com/latentrun/SurgePilot
证据与文档：https://latentrun.github.io/SurgePilot/

欢迎从技术角度检查这套证据。如果它值得继续关注，可以给仓库一个 Star。
```

## Response bank

**“Was there really no human?”**

No. The human set product intent, discussed requirements, used the product, provided feedback, and
accepted results. The original baseline's first-party engineering artifacts and gates were
produced by AI agents. The exact boundary is in `AI-AUTHORSHIP.md`.

**“Which model built each line?”**

The launch does not make model-by-model attribution claims. Its primary evidence is the repository,
governed artifacts, contracts, tests, and the immutable baseline tag.

**“Is this proven in production?”**

No production adoption claim is made. SurgePilot is inspectable, runnable, and backed by explicit
verification gates; readers should evaluate those artifacts directly.

**“Can I contribute without AI?”**

Yes. Future contributions may be human- or AI-authored, with no prompt or model attestation.
