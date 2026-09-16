---
layout: home

hero:
  name: SurgePilot 用户文档
  text: AI 驱动的分布式 API 负载测试
  tagline: 原始公开基线由 AI Agent 构建。设计可复用的请求流程，在多个节点上执行分布式负载测试，并以极低的引擎配置成本查看实时指标。
  image:
    src: /surgepilot-hero.webp
    alt: Illustrative SurgePilot AI load-testing artwork; not a performance benchmark
  actions:
    - theme: brand
      text: 快速开始
      link: /docs/zh-CN/quickstart
    - theme: alt
      text: 启动模式
      link: /docs/zh-CN/startup-modes
    - theme: alt
      text: 术语与常见问题
      link: /docs/zh-CN/faq

features:
  - title: 🤖 原始 AI 构建基线
    details: 原始基线由 AI Agent 在人类指导下完成；职责边界和证据地图均已记录，便于检查。
  - title: ⚡ 一条命令完成 Bootstrap
    details: 运行 `surgepilot up`，即可通过交互式配置在数秒内启动完整技术栈，包括 Web UI、FastAPI 控制平面、PostgreSQL、MinIO、Nginx，以及部署在主机基础设施上的 InfluxDB/Grafana Monitoring。
  - title: 🧾 可检查的工程证据
    details: 治理文档、契约、测试和发布资产让整个系统从产品意图到验证过程都可检查。
  - title: 🌐 分布式 Linux Runner
    details: 控制平面与执行引擎相互解耦。通过 SSH/SFTP 自动管理远程 Linux Load Node，支持多节点指标汇总和实时 InfluxDB 指标流。
  - title: 🔒 数据与 Secret 隔离
    details: 支持多团队 Workspace 隔离、静态加密的 Load Node 凭据、脱敏的 Env Group Secret 变量，以及受契约约束的角色权限检查。
  - title: 📊 权威结论与报告
    details: 通过可复用请求流程和负载模型生成确定性的 PASS/FAIL 结论，并提供详细响应指标、失败明细和可下载的 Run Artifact。
---

## SurgePilot 是什么？

SurgePilot 是一个用于设计、执行和评审 API 负载测试的自托管平台。它将可复用的
请求流程与环境值、负载设置分离，再在一个或多个 Linux Load Node 上执行测试。

SurgePilot 面向开发者、性能工程师和企业内部平台团队，帮助他们在自主管理的
基础设施上建立受控的负载测试工作流。

## 核心工作流

SurgePilot 将测试内容与运行方式、运行位置分离：

- **Scenario** — 定义可复用的 API 和业务请求流程。
- **Env Group** — 提供环境相关的值，无需修改请求流程。
- **Test Plan** — 将 Scenario 与负载设置、执行资源以及通过/失败标准组合起来。
- **Load Node** — 提供执行测试的 Linux 主机。
- **Run Report** — 查看结论、指标、诊断信息和 Artifact。

## 🔄 最短使用路径

1. 按照[快速开始](./quickstart.md)使用 `surgepilot up` 启动完整技术栈。
2. 参考[首次运行](./first-run.md)创建环境、Scenario 和 Test Plan。
3. 关联一个 [Load Node](./first-run.md#prepare-a-load-node)，执行第一次受控 Run。
4. 遇到产品术语或启动边界不明确时，查看[术语与常见问题](./faq.md)。

::: warning 只能测试你有权测试的系统
即使负载很小，也会产生真实流量。请从较低并发和较短持续时间开始，并仅针对
你拥有或已获得明确测试授权的非生产目标进行测试。
:::

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
