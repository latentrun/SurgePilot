# 快速开始

如果你希望在不 Checkout 源码的情况下运行 SurgePilot，请使用 Tagged Release。
如果你正在开发 SurgePilot 本身，请使用源码启动方式。

## 安装 Tagged Release

### 前置条件

- 安装了 Docker Engine 26 或更高版本的 Linux 主机，或者安装了 Docker
  Desktop 26 或更高版本的 macOS 主机。
- Docker Compose 2.27 或更高版本（使用 `docker compose`，而不是旧版
  `docker-compose` 命令）。
- 标准主机工具，包括 `curl` 和 `tar`。
- 首次执行 `up` 时需要交互式 Terminal。

Installer 不会安装或配置 Docker。

### 第 1 步：安装并启动

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

Installer 不使用 `sudo`，不会修改 Shell 启动文件，并将选定 Release 安装到
`${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`。Launcher 会创建在
`$HOME/.local/bin/surgepilot`。

如果该目录不在 `PATH` 中，请使用 Installer 输出的绝对路径命令，或者仅为
当前 Shell 启用该目录：

```sh
export PATH="$HOME/.local/bin:$PATH"
surgepilot up
```

### 第 2 步：确认首次运行配置

在全新部署中，`surgepilot up` 会依次询问：

1. 浏览器和外部 Load Node 使用的 Hostname 或 IP 地址。
2. SurgePilot Web 和 API 流量使用的 HTTP 端口。
3. Load Node 写入 Monitoring 数据时使用的 InfluxDB 端口。

请使用其他计算机和 Load Node 能够访问的地址。本地评估时可以输入
`localhost` 或 `127.0.0.1`，但持久化后的 Node-Facing URL 无法从其他计算机访问。
Docker 仍会在主机网络接口上发布所选端口；如需限制为仅 Loopback 暴露，请使用
主机防火墙。

命令会显示规范化后的非 Secret 配置，并询问
`Use this configuration? [Y/n]`。按 Enter 即可接受。新的 Release 部署会同时选择
两种 Linux Runtime 架构 `amd64,arm64`，并默认禁用 Demo Load Node。

随后，命令会验证并下载匹配的 Runtime Asset，拉取不可变的应用镜像，启动技术栈，
并输出 Web URL。有关生成的 `.env`、Release 网络字段和可选设置，请参阅
[部署配置](./configuration.md)。

### 第 3 步：检查部署

```sh
surgepilot status
surgepilot logs
```

打开 `surgepilot up` 输出的 Web URL，然后继续阅读
[首次运行](./first-run.md)。

停止技术栈但保留 Volume 和 `.env`：

```sh
surgepilot down
```

## 从源码启动

源码启动需要 Git、GNU Make 或兼容实现、POSIX Shell、Perl、`curl`、`tar`/gzip、
SHA-256 校验工具、Docker 和 Docker Compose。在仓库根目录运行：

```sh
make setup
make start-full-stack
```

Make 会下载并校验固定版本的 mise Bootstrap，然后在隔离的 Contributor Namespace 中
安装仓库选定的 Python 3.12、Node.js 22、pnpm 和 uv。它不会修改全局 Runtime 版本或
Shell 启动文件。可使用 `make toolchain-check` 进行离线、无变更诊断，或使用
`make toolchain-install` 显式修复 Managed State。

当根目录不存在 `.env` 时，`make start-full-stack` 会创建安全的本地部署状态，
构建或复用当前原生 Linux 架构的 Load Node Runtime，并启动控制平面、Monitoring
和 Compose 内部的 Demo Load Node。打开 `http://localhost:8080`。

源码模板和 Release 模板有意保持不同。修改源码 `.env` 前，请先阅读
[部署配置](./configuration.md)。

Demo Node 此时正在运行，但还没有注册到产品数据库。开始 Run 前，请按照
[准备 Load Node](./first-run.md#prepare-a-load-node)中的源码 Demo 说明完成配置。

后续可以使用以下命令管理生命周期：

```sh
make restart-full-stack
make stop-full-stack
```

如果只需要评审 UI，而不要求执行就绪，请改用
[源码 Preview](./startup-modes.md#source-preview)。

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
