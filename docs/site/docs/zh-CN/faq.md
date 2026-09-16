# 术语与常见问题

## 核心术语

### 控制平面

保存配置并协调工作的 Web、API、api-worker、PostgreSQL、MinIO、Nginx 和
Monitoring 服务。控制平面本身不会产生负载。

### Runtime

安装在 Load Node 上、带版本的 Linux 执行 Bundle。源码完整技术栈启动会构建或复用
当前原生架构的 Runtime。Tagged Release 会下载并验证选定的预构建 Runtime Asset。

### Load Node

运行独立 SurgePilot Runner 和负载测试引擎的 Linux 计算机。Run 可以选择一个 Node 前，
该 Node 必须已注册、已初始化、可以访问，并且处于 **Idle** 状态。

### Env Group

一组可复用的环境变量。Plain 值保存后仍可读取。Secret 值通过登录后的 UI 接收，
只返回脱敏 Metadata，无法通过产品再次显示明文。

### Scenario

可复用的有序 HTTP Step 流程，包含请求详情和结构化全局配置。Scenario 描述调用什么，
而不是产生多少负载。

### Test Plan

已保存的执行定义，将 Scenario、可选 Env Group、资源选择、每个 Scenario 的负载设置
和可选 SLA Rule 组合起来。

### Debug Run 和 Standard Run

Debug Run 是聚焦的单节点验证路径。Standard Run 使用 Test Plan 的资源与负载配置，
评估 SLA Rule，并可将已启用的指标发送到 Monitoring。

### Run 和 Run Report

Run 是对已保存源码 Revision 的一次执行。Run Report 会显示终态结论、指标、不可变
Snapshot、诊断信息、Artifact 和每个 Node 的状态。

### Preview

“Preview”有两种不同含义：

- **Source preview** 是 `make start-preview`，属于控制平面启动模式，不保证 Runtime、
  Load Node 或 Run 就绪。
- **Generated YAML Preview** 是 Test Plan 的只读视图，展示 API 为最新保存 Revision
  生成的配置，不会启动 Run。

SurgePilot 不提供独立的 Scenario 执行 Preview。

## 常见问题

### 应该使用哪种启动模式？

自托管 Tagged Release 使用 `surgepilot up`。从源码开发或验证完整源码执行路径时使用
`make start-full-stack`。只有在不要求执行就绪的情况下评审登录、UI、控制平面或
Monitoring 时，才使用 `make start-preview`。

### 启动前需要创建或编辑 `.env` 吗？

普通交互式启动不需要。当 `.env` 不存在时，`surgepilot up`、`make start-full-stack`
和 `make start-preview` 都会创建安全的部署状态。Release 首次运行会询问 LAN Host
和端口；源码启动使用源码专用默认值。已有 `.env` 是权威来源，不会被自动覆盖或修复。
手工修改前请参阅[部署配置](./configuration.md)。

### 为什么源码 Preview 中的 Setup Status 显示 `not_configured`？

Preview 会有意跳过 Runtime 准备并禁用 Demo Load Node。因此 Runtime 检查显示
`not_configured` 属于预期行为。需要初始化 Load Node 或执行 Run 时，请启动源码完整技术栈。

### 为什么可以设计 Asset，却无法启动 Run？

创建 Env Group、Scenario 和 Test Plan 不需要执行资源。Run 还需要一个已保存、可运行的
Test Plan，以及一个匹配、已初始化并且当前处于 **Idle** 状态的 Load Node。

### 源码完整技术栈会自动注册 Demo Load Node 吗？

不会。它会启动 Demo SSH Container 并准备 Credential，但 Admin 必须通过
**Load Nodes** 注册节点、验证 Host Key 并完成初始化。

### Tagged Release 包含 Demo Load Node 吗？

Release Bundle 包含可选 Demo Profile，但普通 Release 启动默认禁用它。执行测试时请注册
外部 Linux Load Node。

### Load Node 可以使用 `localhost` 访问 SurgePilot 吗？

如果 Node 运行在另一台计算机或另一个 Container 中，则不可以。此时 `localhost` 指向
Node 自己。请为 Node-Facing API 和 InfluxDB URL 配置 Load Node 能够访问的地址。
Release 首次运行 Prompt 会明确询问该地址。

### `down` 会删除配置或结果吗？

不会。`surgepilot down`、`make stop-full-stack` 和 `make stop-preview` 会停止
Compose 服务，但不会删除部署 `.env` 或 Named Volume。

### 直连 LAN HTTP 适合用于公网吗？

不适合。交互式 Tagged Release Setup 配置的是受信任 LAN HTTP。公网暴露需要由运维人员
管理 HTTPS Reverse Proxy、最终 Node-Facing Origin、Secure Session Cookie、防火墙策略，
并执行常规生产运维控制。

### SurgePilot 可以测试 macOS Load Node 吗？

不可以。macOS 可以通过 Docker Desktop 托管容器化控制平面，但 Load Node 及其 Runtime
只支持 Linux。

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
