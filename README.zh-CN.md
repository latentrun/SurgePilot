# SurgePilot

**一个 100% 由 AI Agent 构建的真实分布式系统。**

![100% AI-Built](https://img.shields.io/badge/original%20baseline-100%25%20AI--authored-8b5cf6) ![Self-Hosted](https://img.shields.io/badge/deploy-self--hosted-06b6d4) ![Contract-First](https://img.shields.io/badge/API-contract--first-22d3ee) ![Coverage Gate](https://img.shields.io/badge/coverage%20gate-%E2%89%A590%25-16a34a) ![License](https://img.shields.io/badge/license-MIT-22c55e)

[English](README.md) | 简体中文 | [日本語](README.ja.md)

**[★ 在 GitHub 上 Star](https://github.com/latentrun/SurgePilot)** · [项目首页](https://latentrun.github.io/SurgePilot/) · [使用文档](https://latentrun.github.io/SurgePilot/docs/zh-CN/) · [Releases](https://github.com/latentrun/SurgePilot/releases)

SurgePilot 是一个自托管的分布式 API 负载测试平台，也是一项可检查的 Agentic Engineering
实验：验证 AI Agent 能否把真实系统从需求与治理推进到架构、实现、验证和发布。它把 API 与业务
流程组织成可复用的 **设计 → 编排 → 运行 → 报告** 闭环，并运行在你控制的基础设施上。

原始公开基线由 AI Agent 在人类指导下端到端完成。人类负责明确产品目标、参与需求讨论并提供反馈、
实际使用产品和验收结果；AI Agent 负责产品的设计、实现、测试、验证、部署与发布。

![SurgePilot 从 AI 辅助测试设计到分布式负载执行与结果分析的工作流](.github/assets/surgepilot-overview.png)

## 亮点

- ⚡ **一条命令启动完整技术栈。** `make start-full-stack` 会启动 Web、API、
  api-worker、PostgreSQL、MinIO、Nginx、Grafana + InfluxDB，以及一个可用的 Demo Load Node。
- 🤖 **从头到尾 100% 由 AI 构建。** PRD → SDD → ADR → Slice →
  契约 → 测试 → 部署，完整生命周期均由 AI 编写，所有产物都保存在本仓库中。
- 🧭 **有章可循，不靠“感觉编程”。** `AGENTS.md`、范围门禁、ADR 和
  契约优先规则让每一项变更都有清晰边界，并且便于审核。
- 🔒 **明确的安全边界。** 支持 Workspace 隔离、基于角色的管理权限、
  加密的 Load Node 凭据，以及范围受控的公共 REST API。
- 🌐 **真正的分布式执行。** API 通过 SSH 驱动远程 Load Node 上相互独立的 Runner，
  汇总多节点测试结果，并将指标流式写入 InfluxDB。
- 🧩 **AI 原生基础设施。** 内置经过治理的 AI Skill 包，让 Claude、Codex 等 Agent
  能直接操作负载测试；使用 PAT 认证、限定 Workspace 范围，并强制确认写操作。
- ✅ **验证不是可选项。** `make verify` 会强制执行 lint、测试、≥90% 覆盖率门禁和
  契约新鲜度检查，并由真实 SSH 端到端测试配置提供保障。

## SurgePilot 能做什么

性能团队常常会遇到相同的问题：负载测试脚本通常是一次性的，难以复用；每套环境都要从头配置；
一次测试需要手工连接多台负载机；最终结果又散落在各处，很难依据既定目标快速判断是否达标。

SurgePilot 将这些工作收敛为一套可复用、可编排、可追溯的闭环。你可以把 API 和业务流程制作成
一次设计、跨环境重复使用的测试资产，再通过负载模型和通过/失败标准完成编排，在多个 Load Node
上分布式执行，最后得到一份权威报告，集中查看测试结论、关键指标和 Artifacts。这样一来，你可以
专注于*要测试什么、测试结果如何*，而不必陷入底层执行引擎的配置细节。

而且，这些操作并不要求你逐页点击 UI。SurgePilot 可以与 AI Agent 集成：搭配下文介绍的内置
AI Skill 后，Claude、Codex 等工具就能通过受治理、经过权限校验的路径，以对话方式启动、执行并
检查负载测试。

## 100% 由 AI 构建

SurgePilot 展示了一种受治理、由 AI 驱动的工程实践，而不是一次性生成。整个系统遵循一套明确、
可审计的生命周期完成构建：

完整的作者范围见 [AI 作者说明](AI-AUTHORSHIP.md)。

| 阶段 | AI 产物 | 使用的 AI 工具 | 仓库中的依据 |
|---|---|---|---|
| 1. 产品 | 产品需求文档 | GPT · Gemini | [`docs/prd`](docs/prd/PRD.md) |
| 2. UI/UX | 前端界面与体验 | Claude · Gemini · Google Stitch | [`apps/web`](apps/web) |
| 3. 系统设计 | SDD、范围门禁、ADR 和已接受的 Slice | GPT · Claude | [`docs/sdd`](docs/sdd/README.md) · [`adr`](docs/sdd/adr/README.md) · [`slices`](docs/sdd/slices/P2-README.md) |
| 4. 编码实现 | 应用代码与 API 契约 | GPT | [`packages/contracts`](packages/contracts) · [`apps`](apps) |
| 5. 验证 | Review 修复、测试和门禁 | GPT · Claude | [`Makefile`](Makefile) · [测试策略](docs/sdd/09-testing-and-acceptance-strategy.md) |
| 6. 发布 | 启动、部署与发布资产 | GPT | [`infra/release`](infra/release) · [Workflows](.github/workflows) |

这里没有黑盒：上表中的每一个阶段都链接到仓库里的真实产物。
[`AGENTS.md`](AGENTS.md) 是让这套流程能够重复执行的机器可读契约——修改代码前先加载相关范围，
先更新契约再更新消费者，遵守 API/Runner 边界，并通过所有验证门禁。最终得到的是一个可以检查、
复现和扩展的分布式系统，而不是一堆缺乏治理的生成文件。

## 架构

SurgePilot 是一个**分布式、多服务系统**：Web 前端与 API 后端相互解耦，后台 Worker 独立运行，
Runner 分布在多个远程节点上并行产生负载，再通过文档化协议回传结果。（源码存放在同一个
monorepo 中，但运行时并不是单体应用。）这些服务之间清晰且被严格执行的边界，是系统安全性、
可靠性和独立扩缩容能力的基础：

![SurgePilot 系统架构图](docs/site/public/surgepilot-architecture.jpg)

## 主要能力

以下能力按照企业内部平台团队的实际评估维度分类。每一项都有仓库中的 Route、生成契约和测试作为
依据；各项功能的具体用法属于产品文档范围，不在此概览中展开。

- **团队隔离与访问控制。** 支持多团队 Workspace、按 Workspace 隔离数据、User Management，
  并由后端强制执行 admin/user 角色权限。
- **凭据与 Secret 安全。** Load Node 凭据加密存储（只写且永不回显），Env Group 变量支持
  `plain | secret` 类型并在读取时脱敏，同时为敏感操作记录审计事件。
- **核心测试流程。** Visual Scenario 设计、cURL 导入、根据 OpenAPI Operation 生成 Step 草稿、
  Test Plan 编排、受控的 Run 执行、Run Report、Artifacts 和 Debug HTTP Trace。
- **规模与可观测性。** 支持多节点分布式 Run 执行和结果汇总，并提供只读 Monitoring
  （Grafana + InfluxDB），由各节点流式写入指标。
- **自动化与集成。** 提供经过 PAT 认证、范围受控的公共 REST API、生成的公共 OpenAPI 产物、
  API Catalog，以及用于 Agent 驱动操作的受治理 AI Skill 包。
- **自托管运维。** 一条命令启动完整技术栈、契约优先架构，以及 ≥90% 覆盖率验证门禁。

具体可用能力由已激活的 Slice SDD 和 ADR 管理。本仓库**不会**把尚未激活的路线图能力——例如
定时调度、通用 Secret Manager 集成、可编辑的原始引擎配置、SSO 或 Kubernetes——描述成
已经可用的功能。

## AI-Native：通过你的 AI Agent 操作 SurgePilot

SurgePilot 将 AI Agent 视为一等操作入口，而不是后续附加功能。它以通用的 `SKILL.md` 格式提供
经过治理的 **Public API AI Skill 包**，让 **Claude**、**Codex** 等 Coding Agent 能通过安全、
受契约约束的路径操作平台，而不必猜测 HTTP 调用方式。

**一键获取：**登录用户可以在应用内打开 **Help → AI Agents** Tab，直接从 UI 下载可立即使用的
Skill 压缩包（`surgepilot-public-api-skill.zip`），无需检出仓库或执行构建。将 Agent 指向
解压后的目录，即可开始操作 SurgePilot。

该 Skill 封装了范围受控的公共 REST API 及其生成的 OpenAPI 契约：

- **经过认证并限定范围。** 调用使用 Personal Access Token（PAT）和明确指定的 Workspace；
  Agent 不会接触浏览器 Session、Cookie 或其他 Workspace。
- **默认安全。** 每个 `POST`/`PATCH`/`DELETE` 操作——包括创建或停止 Run——都会先展示预览，
  只有得到明确确认后才会执行。遇到任何未声明的状态或字段时，Skill 会以失败关闭方式停止执行。
- **受契约约束。** Agent 只调用内置 OpenAPI 契约中 Allowlist 允许的 `operationId`，
  绝不会自行拼接原始 URL。

应用会在收到请求时构建压缩包并发送到浏览器；其底层是由本仓库维护的源码包，而不是 SDK、
MCP Server、Marketplace 或 Installer。

## 快速开始

前置条件：Docker Engine/Desktop 26 或更新版本，以及 Docker Compose 2.27 或更新版本。Installer 还需要标准主机工具、`curl` 和 `tar`。

```bash
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

`surgepilot up` 会确认首次启动配置、下载经过校验的 Linux Runtime 资产、启动自托管技术栈并输出 Web URL。新的 Release 部署默认关闭 Demo Load Node，因此执行 Run 前需要准备一个外部 Linux Load Node。

- [完整快速开始](https://latentrun.github.io/SurgePilot/docs/zh-CN/quickstart)
- [第一次运行](https://latentrun.github.io/SurgePilot/docs/zh-CN/first-run)
- [配置参考](https://latentrun.github.io/SurgePilot/docs/zh-CN/configuration)

### 从源码启动

用于开发或完整的本地源码执行路径：

```bash
make setup
make start-full-stack
```

在官方源码启动路径下，SurgePilot 会准备或复用当前原生架构的 Linux Runtime，并默认启动 Compose 内部 Demo Load Node。执行 Run 前，仍需在 SurgePilot 中注册并初始化该 Demo 节点。Demo Profile 可以通过源码配置显式关闭。

只查看登录页、UI、控制平面和 Monitoring，而不需要 Runtime 或 Run readiness 时，请使用 `make start-preview`。不同模式的精确保证请参阅[启动模式](https://latentrun.github.io/SurgePilot/docs/zh-CN/startup-modes)。

## 使用本仓库评测新模型

由于完整工程生命周期都保存在仓库中，本仓库可以作为一个更高维度的 Benchmark：它评估模型能否
依据真实材料重建或扩展一个多服务系统，而不仅仅是生成一个浅层界面。给模型一组范围明确的
PRD、SDD、ADR、Slice、契约和测试输入，然后从以下方面进行对比：

- 是否能重建 P0 产品闭环，以及最终 `make verify` 的执行结果；
- 是否能实现一个已接受、已有支持的 Slice 扩展，并检查契约差异、生成 Client 的新鲜度和测试；
- 是否能重新生成公共 OpenAPI，并确认其中没有出现禁止的 Route 和 Schema；
- 是否能保持 Workspace/安全规则，以及 API/Runner 协议边界；
- 是否能避免引入未激活的 P1/P2 能力和禁止使用的基础设施。

在 Make Target 和运行环境均支持的情况下，仓库还提供
`make verify-p2-02-public-api-lifecycle`，用于验证 Public API Lifecycle 场景。

## 文档

### 用户文档

- [文档首页](https://latentrun.github.io/SurgePilot/docs/zh-CN/)
- [快速开始](https://latentrun.github.io/SurgePilot/docs/zh-CN/quickstart)
- [启动模式](https://latentrun.github.io/SurgePilot/docs/zh-CN/startup-modes)
- [配置](https://latentrun.github.io/SurgePilot/docs/zh-CN/configuration)
- [第一次运行](https://latentrun.github.io/SurgePilot/docs/zh-CN/first-run)
- [常见问题](https://latentrun.github.io/SurgePilot/docs/zh-CN/faq)

### 贡献者与评审者文档

- [贡献指南](CONTRIBUTING.md)和 [Agent 规则](AGENTS.md)
- [SDD 入口](docs/sdd/README.md)和[范围门禁](docs/sdd/00-product-scope-and-priority.md)
- [架构概览](docs/sdd/01-architecture-overview.md)和[开发流程](docs/sdd/02-repo-structure-and-dev-workflow.md)
- [API 契约](docs/sdd/04-api-contract-guidelines.md)和 [Runner 协议](docs/sdd/05-runner-protocol-and-run-state-machine.md)
- [测试策略](docs/sdd/09-testing-and-acceptance-strategy.md)
- [ADR 索引](docs/sdd/adr/README.md)、[P1 Slice 索引](docs/sdd/slices/P1-README.md)和 [P2 Slice 索引](docs/sdd/slices/P2-README.md)

## 贡献

提交变更前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [AGENTS.md](AGENTS.md)。贡献可以由人类或 AI 完成；评审依据是提交内容和仓库契约。

Host-mode 开发、数据库迁移、契约生成和验证请遵循[开发流程](docs/sdd/02-repo-structure-and-dev-workflow.md)以及当前 [`Makefile`](Makefile)，不要从 README 摘要推断命令行为。

## 许可证

SurgePilot 使用 [MIT License](LICENSE)。
