# 部署配置

SurgePilot 将部署设置保存在根目录 `.env` 文件中。普通用户无需手工创建该文件：
官方启动命令会在首次运行时创建它、生成私有值、验证结果，并保留给后续启动使用。

## 选择正确的模板

SurgePilot 有意提供两个模板，因为 Release 和源码生命周期在网络、Runtime 和构建方面
有不同要求。

| 部署方式 | 仓库中的模板 | 常用命令 |
| --- | --- | --- |
| Tagged Release | `infra/release/.env.example`，安装后以 `.env.example` 位于 Release 目录 | `surgepilot up` 或 `./surgepilot up` |
| 源码 Checkout | 根目录 `.env.example` | `make start-full-stack` 或 `make start-preview` |

不要用一个模板覆盖另一个模板。Release 模板要求最终的 Node-Facing LAN Origin 和
Secure Cookie 意图。源码模板包含开发端口、源码构建 Mirror 和本地生成的 Runtime 输入，
这些内容不属于 Release 部署。

## `.env` 的管理方式

1. 如果缺少 `.env`，官方启动流程会复制正确模板、生成私有 Bootstrap 值，并写入
   仅文件所有者可访问的部署状态。
2. 如果 `.env` 已存在，启动流程会将其视为权威来源，不会覆盖、轮换或修复现有值。
3. 通过进程环境显式提供的 Bootstrap 值只会在首次创建时持久化。后续启动时提供冲突值
   会失败关闭。
4. Release 首次运行会询问 Host 和两个发布端口，然后持久化最终的 API 与 InfluxDB
   Node-Write Origin。后续交互式启动时，在配置确认中回答 **No**，只能更新这四个网络字段。
5. 源码启动不使用 Release 重配置流程。如需覆盖，请有意识地编辑源码 `.env`。

手工修改后，Release 运行 `surgepilot up`，正在运行的源码技术栈运行
`make restart-full-stack`。两种方式都会在启动服务前验证实际配置。

::: danger 保持生成的 Secret 稳定
不要通过编辑 `.env` 轮换部署 Secret。特别是，丢失或修改 SSH 凭据加密密钥会导致
已存储的 Load Node 凭据无法读取。已有数据库和对象存储 Volume 也会保留初始化时使用的身份。
:::

## 如何阅读配置参考

- **无需配置**表示生成值或模板值适合普通使用。
- **首次运行**表示 Release Prompt 会提供部署专用值。
- **按需配置**表示只在所述部署模式下修改。
- **高级配置**表示没有明确运维原因和重启计划时应保持不变。
- **托管值**表示由官方启动或 Runtime 命令提供，正常使用时不要手工持久化。
- **不存在**表示该模板不提供此设置。

## 启动和网络设置

| 变量 | Release | 源码 | 是否配置？含义 |
| --- | --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `surgepilot` | `surgepilot` | **无需配置。** Docker Compose 资源命名空间。修改它会选择另一套技术栈和另一组 Named Volume。 |
| `SURGEPILOT_HTTP_PORT` | `8080` | `8080` | **Release 首次运行；源码按需配置。** Nginx 为 Web UI、API 和 Grafana 路径发布的主机端口。请选择空闲端口。 |
| `POSTGRES_HOST_PORT` | 不存在 | `5432` | **仅源码，按需配置。** 源码 PostgreSQL 服务发布的主机端口。Release PostgreSQL 不会对外发布。 |
| `SURGEPILOT_API_HOST_PORT` | 不存在 | `8000` | **仅源码，按需配置。** 源码 API Container 的直连主机端口，与常规 Nginx 入口相互独立。 |
| `DEFAULT_WORKSPACE_NAME` | `Default Workspace` | `Default Workspace` | **按需配置。** 首位 Admin 创建初始 Workspace 时使用的名称，不会重命名已有 Workspace。 |
| `SURGEPILOT_NODE_API_BASE_URL` | 有效 LAN 示例，首次运行时替换 | 注释示例 | **Release 首次运行；源码外部节点按需配置。** Load Node 可访问的最终 API Origin。缺少该值时，源码 Demo 使用 Compose 内部 Origin。DB 中的 System Setting 可以覆盖应用 Fallback。 |
| `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT` | `8086` | `8086` | **Release 首次运行；源码按需配置。** 为已认证 Load Node 写入 InfluxDB 而发布的主机端口，必须与 HTTP 端口不同。 |
| `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` | 有效 LAN 示例，首次运行时替换 | 注释示例 | **Release 首次运行；源码外部节点按需配置。** Load Node 可访问的最终 InfluxDB Origin。请与 Node API Origin 一起设置。 |
| `SESSION_COOKIE_SECURE` | `false` | 不存在 | **按需配置。** Release HTTP 模式要求为 `false`；由运维管理的 HTTPS 部署设为 `true`，并使用 HTTPS Node API Origin。 |
| `SURGEPILOT_DEMO_LOAD_NODE_ENABLED` | `false` | `true` | **按需配置。** 启用可选的 Compose 内部 Demo Load Node。Release 默认关闭；源码完整技术栈默认开启；Preview 会在不重写 `.env` 的情况下强制关闭。 |
| `SURGEPILOT_RUNTIME_ARCHITECTURES` | `amd64,arm64` | `auto` | **正常启动无需配置。** 为 Load Node Runtime Asset 准备的架构。Release 首次运行保留两种受支持架构；源码 `auto` 选择 Docker Daemon 的原生架构。有效值为 `auto`、`amd64`、`arm64` 和 `amd64,arm64`。 |
| `APP_ENV` | 不存在 | `development` | **仅源码直连主机开发。** 选择应用环境默认值。官方 Compose 会提供固定值。 |
| `DATABASE_URL` | 不存在 | 本地 PostgreSQL URL | **仅源码直连主机开发。** `make dev-api`、`make dev-worker` 和 Compose 外迁移使用的数据库连接。官方 Compose 会提供内部 URL。 |
| `MINIO_ENDPOINT` | 不存在 | `http://localhost:9000` | **仅源码直连主机开发。** Compose 外 API 进程使用的 MinIO Endpoint。官方 Compose 会提供内部 Endpoint。 |

## 部署身份、Secret 和 MinIO

| 变量 | 模板值 | 是否配置？含义 |
| --- | --- | --- |
| `RUNNER_INTERNAL_TOKEN` | Placeholder 会替换为随机 Token | **托管值。** API 与 Runner 之间使用的共享内部认证材料。必须保持私有且稳定。 |
| `SSH_CREDENTIAL_ENCRYPTION_KEY` | Placeholder 会替换为随机 Base64 Key | **托管值。** 用于保存 Load Node 凭据的 AES-256-GCM Key。解码后必须恰好为 32 字节，并在复用数据库期间保持稳定。 |
| `MINIO_BUCKET` | `surgepilot` | **无需配置。** Dependency File 和 Run Artifact 使用的对象存储 Bucket。 |
| `MINIO_ACCESS_KEY` | `minioadmin` | **内置服务无需配置。** API 侧 MinIO 访问身份，必须与内置部署中的 MinIO Root User 相同。 |
| `MINIO_SECRET_KEY` | Placeholder 会替换为随机密码 | **托管值。** API 侧 MinIO Secret，必须与内置部署中的 MinIO Root Password 相同。 |
| `MINIO_ROOT_USER` | `minioadmin` | **内置服务无需配置。** MinIO 初始化用户，必须与 Access Key 一致。 |
| `MINIO_ROOT_PASSWORD` | 与 MinIO Secret 相同的生成值 | **托管值。** MinIO 初始化密码，必须与 API 侧 Secret 一致。修改它不会重新初始化已有 MinIO Volume。 |
| `MINIO_REGION` | 已注释 | **高级配置，仅直连主机。** 当 Endpoint 本身无法确定 Region 时，传给 MinIO Client 的可选 Region。官方 Compose 不传递该覆盖值。 |
| `MINIO_SECURE` | 已注释，默认 `false` | **高级配置，仅直连主机。** 当直连主机 MinIO Endpoint 不含 Scheme 时启用 TLS。显式 `https` Endpoint 已经会选择 TLS。 |

## Monitoring Bootstrap 和链接

| 变量 | 模板值 | 是否配置？含义 |
| --- | --- | --- |
| `SURGEPILOT_MONITORING_INFLUXDB_USERNAME` | `surgepilot` | **普通首次运行无需配置。** InfluxDB 初始化用户名。不要期望修改后能重新初始化已有 Volume。 |
| `SURGEPILOT_MONITORING_INFLUXDB_PASSWORD` | Placeholder 会替换为随机密码 | **托管值。** InfluxDB 初始化密码。不能以 `-` 开头，否则 Setup CLI 会将其解析为 Flag。 |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST` | 示例路径会替换为私有生成文件 | **托管值。** 作为 InfluxDB Token Secret 挂载的主机路径。官方启动会创建私有 Token 文件，并为所选布局写入正确路径。 |
| `SURGEPILOT_MONITORING_INFLUXDB_ORG` | `surgepilot` | **无需配置。** Setup、Backend Listener 和 Monitoring 链接使用的 InfluxDB Organization。 |
| `SURGEPILOT_MONITORING_INFLUXDB_BUCKET` | `jmeter` | **无需配置。** 接收 Standard Run 指标的 InfluxDB Bucket。 |
| `SURGEPILOT_GRAFANA_ADMIN_USER` | `admin` | **按需配置。** Grafana Bootstrap Admin 用户名。如需其他名称，请在 Grafana Volume 初始化前设置。 |
| `SURGEPILOT_GRAFANA_ROOT_URL` | 已注释，Grafana 子路径表达式 | **高级配置。** Grafana 在 `/grafana/` 下提供服务时使用的 Server Root URL。模板值匹配内置 Proxy 布局。 |
| `SURGEPILOT_MONITORING_DASHBOARD_UID` | 已注释，`surgepilot-jmeter-13644` | **高级配置。** 用于构建预置只读 JMeter Dashboard 链接的 UID。只能与匹配的 Grafana Provisioning 一起修改。 |
| `SURGEPILOT_MONITORING_DASHBOARD_SLUG` | 已注释，`jmeter-load-test` | **高级配置。** 用于构建预置 Dashboard 链接的 Slug。只能与匹配的 Grafana Provisioning 一起修改。 |
| `SURGEPILOT_MONITORING_ENABLED` | 已注释，直连主机 API 默认 `false` | **仅直连主机。** 官方完整技术栈 Compose 会显式启用 Monitoring，因此该 `.env` 覆盖值不会禁用内置 Monitoring。 |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED` | 已注释，直连主机 API 默认 `false` | **仅直连主机。** 告知直接启动的 API 是否已从外部配置 Monitoring Token 状态。官方 Compose 会提供正确值。 |
| `SURGEPILOT_MONITORING_GRAFANA_BASE_PATH` | 已注释，`/grafana` | **仅直连主机。** 生成 Grafana 链接使用的 Base Path。官方 Compose 将内置路径固定为 `/grafana`。 |
| `SURGEPILOT_MONITORING_TIME_PADDING_SECONDS` | 已注释，`60` | **高级配置。** 生成 Monitoring 链接时在 Run 时间范围前后增加的秒数。 |

InfluxDB 初始化用户名、密码、Organization 和 Bucket 不能以 `-` 开头，否则 InfluxDB
Setup CLI 会将该值解析为 Flag。

## 源码 Runtime 和镜像构建设置

这些设置仅存在于源码模板中。Tagged Release 会拉取锁定版本的应用镜像和经过验证的
Runtime Asset，而不是从源码构建。

| 变量 | 模板值 | 是否配置？含义 |
| --- | --- | --- |
| `LOAD_NODE_RUNTIME_VERSION` | 已注释 | **托管值。** 官方 Runtime Builder 写入生成的 `runtime.env` 状态中的 Runtime 版本。 |
| `LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR` | 已注释的绝对路径示例 | **托管值。** 写入生成 Runtime 状态并以只读方式挂载到 API 服务的主机目录。 |
| `SURGEPILOT_SKIP_RUNTIME_PREFLIGHT` | 已注释，`1` | **仅限高级手工/Debug。** 跳过源码完整技术栈启动的 Runtime 准备。不会跳过部署 Bootstrap，也不保证 Load Node 或 Run 就绪。 |
| `RUNTIME_JMETER_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 JMeter 下载的可选预期 Checksum。 |
| `RUNTIME_CASUTG_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 Concurrency Thread Group Plugin 的可选预期 Checksum。 |
| `RUNTIME_JSON_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 JSONPath Plugin 的可选预期 Checksum。 |
| `RUNTIME_TST_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 Throughput Shaping Timer Plugin 的可选预期 Checksum。 |
| `RUNTIME_RANDOM_CSV_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 Random CSV Data Set Plugin 的可选预期 Checksum。 |
| `RUNTIME_INFLUXDB2_LISTENER_SHA256` | 已注释 | **高级配置。** 提供给源码 Runtime Builder、用于 InfluxDB2 Listener Plugin 的可选预期 Checksum。 |
| `SURGEPILOT_PIP_INDEX_URL` | 已注释的 Mirror 示例 | **按需配置。** 源码 Docker Build 和 Runtime Builder 使用的 Python Package Index。保持未设置会使用 Upstream 默认值。 |
| `SURGEPILOT_NPM_REGISTRY` | 已注释的 Mirror 示例 | **按需配置。** 源码 Web 镜像构建使用的 npm Registry。保持未设置会使用 Upstream 默认值。 |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR` | 已注释的无效示例 | **按需配置。** 仅在源码 Docker Build 期间使用的 Ubuntu Package Mirror。启用前请替换为真实 Mirror。 |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR` | 已注释的无效示例 | **按需配置。** 仅在源码 Docker Build 期间使用的 Ubuntu Security Mirror。 |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR` | 已注释的无效示例 | **按需配置。** 仅在源码 Docker Build 期间使用的 Debian Package Mirror。 |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR` | 已注释的无效示例 | **按需配置。** 仅在源码 Docker Build 期间使用的 Debian Security Mirror。 |
| `VITE_API_BASE_URL` | 已注释的直连 API 示例 | **高级配置，仅源码构建。** Web Client 的 Build-Time Seed。内置 Web Runtime 使用同源 `/api`，普通部署保持未设置。 |

## DB 支持的 System Setting Fallback

以下 `.env` 值只在对应数据库 System Setting 不存在时使用。普通策略修改应通过
**Admin → System Settings** 完成，而不是编辑 `.env`。修改环境 Fallback 后需要重启
部署才能加载；已有 DB 值仍然优先。

| 变量 | Fallback | 含义 |
| --- | --- | --- |
| `ALLOW_SIGNUP` | `true` | 首位 Admin 之后的用户是否可以注册。Setup 未完成时，首位 Admin Bootstrap 始终可用。 |
| `DEPENDENCY_FILE_MAX_BYTES` | `104857600` | Dependency File 上传大小上限，单位为字节。 |
| `DEPENDENCY_FILE_ALLOWED_EXTENSIONS` | 空 | 逗号分隔的 Allowlist。空表示不应用扩展名 Allowlist；文件名安全检查仍然生效。 |
| `DEPENDENCY_FILE_PREVIEW_MAX_BYTES` | `65536` | 单文件文本 Preview 返回的最大字节数。 |
| `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS` | 模板扩展名列表 | 永远不会作为文本 Preview 呈现的逗号分隔扩展名。 |
| `SURGEPILOT_MAX_SCENARIO_ITEMS_PER_TEST_PLAN` | `20` | 一个 Test Plan 中启用的 Scenario Item 上限。 |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT` | `1000` | 需要显式高并发确认的单节点并发阈值。 |
| `SURGEPILOT_MAX_RUN_DURATION_SECONDS` | `86400` | 配置的 Run 最大持续时间。 |
| `SURGEPILOT_MAX_RAMP_UP_SECONDS` | `86400` | Ramp-Up 最大持续时间；不能超过实际 Run 持续时间限制。 |
| `SURGEPILOT_MAX_DELAY_SECONDS` | `86400` | 配置的最大启动延迟。 |
| `SURGEPILOT_MAX_ITERATIONS` | `1000000` | Iteration-Based Load Model 的最大迭代次数。 |
| `SURGEPILOT_MAX_TARGET_RPS` | `100000` | Load Model 验证允许的最大目标 RPS。这是配置上限，不代表性能承诺。 |
| `SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN` | `5` | Standard Test Plan 中启用的 SLA Rule 上限。 |
| `SURGEPILOT_JMETER_MEMORY_XMX` | `4G` | 写入执行配置的 JMeter 最大 Heap。有效值为正整数后跟 `K`、`M` 或 `G`。 |

## 高级运维 Guardrail

以下值已有应用和 Compose 默认值。除非实测行为证明需要修改，否则请保持注释状态。
修改后需要重启。

### Load Node 初始化

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS` | `30` | Load Node 初始化期间单条命令的 Timeout。 |
| `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS` | `120` | 在 Load Node 上安装 Runtime 的 Timeout。 |
| `LOAD_NODE_DEFAULT_RUNNER_HOME` | `/opt/surgepilot/runner` | Load Node 未指定其他路径时使用的默认远程 Runner Home。 |
| `LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS` | `15` | Load Node 操作的 SSH 连接 Timeout。 |
| `LOAD_NODE_INIT_TIMEOUT_SECONDS` | `120` | 用于恢复过期初始化尝试和遗留在初始化状态节点的时间阈值。 |
| `LOAD_NODE_INIT_LOG_TAIL_BYTES` | `65536` | 为状态和失败报告保留的初始化日志 Tail 最大字节数。 |
| `LOAD_NODE_GENERATED_KEY_TYPE` | `ed25519` | SurgePilot 生成 Load Node Keypair 时使用的 SSH Key 类型。 |

### Run 控制和 Artifact

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS` | `60` | Runner 接受后等待执行开始的最长时间，以及执行开始后的最大 Heartbeat 间隔。 |
| `SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS` | `120` | 等待 Runner 接受远程请求 Allocation 的最长时间。 |
| `SURGEPILOT_RUN_STOP_GRACE_SECONDS` | `60` | 进入 Force-Kill 处理前，允许正常停止的 Grace Period。 |
| `SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS` | `30` | Force-Kill 控制使用的 SSH Timeout。 |
| `SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS` | `30` | 持久化 Runner Callback Record 的保留天数。 |
| `SURGEPILOT_RUN_CONTROL_STALE_SECONDS` | `120` | 已认领 Run-Control Work 被视为过期并进入恢复的时间。 |
| `SURGEPILOT_NODE_COOLDOWN_SECONDS` | `300` | Force-Kill 后，该 Load Node 可以再次被分配前的 Cooldown Period。 |
| `SURGEPILOT_RUN_ARTIFACT_MAX_BYTES` | `209715200` | 普通 Run Artifact 可接受的最大大小。 |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES` | `1048576` | Run 已进入终态后可接受的最大 Artifact 大小。 |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS` | `300` | Run 进入终态后，允许接受受限 Late Artifact 的时间窗口。 |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT` | `10000` | 单节点并发硬上限。不能通过确认绕过，也不能在 DB 中编辑。 |

### API Catalog 和 Debug HTTP Trace

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES` | `10485760` | 上传 API Catalog Spec 的最大大小。 |
| `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS` | `100` | 一次 Debug HTTP Trace 保留的 Request Record 上限。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES` | `65536` | 每条 Trace Record 内联保留的 Request 或 Response Body 最大字节数。 |
| `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES` | `10485760` | 接受并解析的 Debug HTTP Trace Artifact 最大大小。 |
| `SURGEPILOT_DEBUG_TRACE_RECORD_MAX_BYTES` | `131072` | 单条 Trace Record 的最大编码大小。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_MAX_BYTES` | `5242880` | 单个独立存储的 Trace Body Blob 最大大小。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES` | `20971520` | 单个 Trace Artifact 中独立存储的 Trace Body 总字节上限。 |

## 手工编辑之前

1. 确认该值属于 Release 模板还是源码模板。
2. 如果设置标记为**托管值**，请停止修改。
3. 保持 `.env` 的所有权和仅文件所有者可访问的权限。
4. 永远不要提交 `.env` 或生成的 Secret 文件。
5. 修改 Release 网络配置时，优先使用 `surgepilot up` 确认流程，而不是直接编辑。
6. 修改后运行官方启动命令，并在服务启动前查看其实际配置摘要。

有关启动行为和支持的模式，请继续阅读
[启动模式](./startup-modes.md)。产品术语请参阅
[术语与常见问题](./faq.md)。

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
