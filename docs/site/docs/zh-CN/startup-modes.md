# 启动模式

SurgePilot 提供一种 Tagged Release 模式和两个源码 Checkout 入口。请根据需要验证的
内容选择模式，而不是简单选择启动速度最快的命令。

| 模式 | 适用场景 | Runtime | Demo Load Node | 应用源码构建 |
| --- | --- | --- | --- | --- |
| Tagged Release | 自托管部署 | 新部署会下载经过验证的 `amd64` 和 `arm64` Asset | 默认禁用 | 不构建；拉取锁定 Digest 的镜像 |
| 源码完整技术栈 | 开发和完整的本地执行路径 | 构建或复用当前原生 Linux Runtime | 启动后由用户注册并初始化 | 是 |
| 源码 Preview | 登录、UI、控制平面和 Monitoring 评审 | 不准备 | 禁用 | 是 |

所有模式都使用持久化部署状态，但 Release 和源码 Checkout 使用不同的 `.env` 模板。
有关字段和首次运行行为，请参阅[部署配置](./configuration.md)。

## Tagged Release

安装 Release 后，使用当前用户的 Launcher：

```sh
surgepilot up
surgepilot status
surgepilot logs
surgepilot down
```

如果你手动下载并验证了带版本的 Release Archive，请在解压目录中使用
`./surgepilot up`、`./surgepilot status`、`./surgepilot logs` 和
`./surgepilot down` 执行相同的生命周期操作。

Release 会启动 Web、API、api-worker、PostgreSQL、MinIO、Nginx、InfluxDB
和 Grafana。它不会在部署主机上构建应用源码或编译 Runtime。Load Node 及其 Runtime
仍然只支持 Linux；macOS 支持是指容器化控制平面可以通过 Docker Desktop 运行。

每次有效的 `up` 都会在获取 Runtime 前显示实际的 Web/API Endpoint、InfluxDB
Node-Write Endpoint、Runtime 架构和 Demo 状态。对于已有且有效的 `.env`，回答 Yes
或按 Enter 会原样接受，不会重写。在非交互环境中，如果缺少 `.env`，命令会失败关闭；
自动化流程必须预先提供完整且仅文件所有者可访问的 `.env`。

生成的直连 LAN 配置使用 HTTP，面向受信任网络。互联网部署需要由运维人员管理 HTTPS
Reverse Proxy，配置最终可从外部访问的 Node-Facing Origin，并设置
`SESSION_COOKIE_SECURE=true`。这些高级配置需要显式编辑 `.env`，首次运行 Prompt
不会配置 TLS。

## 源码完整技术栈

使用官方的完整源码入口：

```sh
make start-full-stack
```

首次使用时，该命令会创建根目录 `.env` 和私有本地状态。随后准备当前原生架构的
Runtime、验证完整 Compose 配置、构建应用镜像，并启动 Monitoring 和 Compose 内部的
Demo Load Node。默认 Web URL 为 `http://localhost:8080`。

Demo Node 仍需在 SurgePilot 中完成注册和初始化，Run 才能选择它。请参阅
[准备 Load Node](./first-run.md#prepare-a-load-node)。

```sh
make restart-full-stack
make stop-full-stack
```

这两个生命周期命令都会保留根目录 `.env`、私有状态和 Compose Volume。
重启 Preflight 会在停止正在运行的技术栈之前完成。

## 源码 Preview {#source-preview}

只有在不准备执行资源的情况下查看登录页面、产品 UI、控制平面行为或 Monitoring 时，
才使用 Preview：

```sh
make start-preview
```

Preview 会启动 Web、API、api-worker、PostgreSQL、MinIO、Nginx、InfluxDB 和
Grafana。它会有意跳过 Runtime 准备并禁用 Demo Load Node。Setup Status 可能显示
`not_configured`；此模式不保证 Load Node 初始化或 Run 执行就绪。

打开 `http://localhost:8080`。停止 Preview 但不删除 Volume：

```sh
make stop-preview
```

Preview 和源码完整技术栈使用相同的安全根目录部署状态。需要完整执行路径时，请切换到
`make start-full-stack`。

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
