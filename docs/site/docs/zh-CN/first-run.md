# 第一次 Run

本指南会建立最小可用闭环：环境值 → Scenario → Test Plan → Run → Report。

开始前，请先启动 [Tagged Release 或源码完整技术栈](./quickstart.md)。源码 Preview
不会准备 Runtime 或 Load Node，因此无法满足本指南要求。

::: warning 使用安全的测试目标
请选择你拥有或已获得明确测试授权的非生产 Endpoint。首次测试保持一个并发用户，
持续 60 秒。
:::

## 第 1 步：注册首位 Admin

打开启动命令输出的 Web URL，选择 **Sign up**。第一个账号会成为 Admin，并创建
**Default Workspace**。后续注册遵循当前部署的 Signup Policy。

## 第 2 步：创建 Env Group

Env Group 将环境专用值与可复用 Scenario 分开保存。

1. 打开 **Assets → Env Groups**。
2. 选择 **New Env Group**。
3. 将其命名为 `local`。
4. 添加一个 Plain Variable，Key 为 `base_url`，Value 为测试目标的完整 Origin，
   例如 `https://test-api.example.com`。
5. 选择 **Save Env Group**。

不要为 `base_url` 选中 **Secret**。Secret 值是只写的，保存后会被脱敏；它们用于
凭据，不适合普通目标地址。

## 第 3 步：准备 Load Node {#prepare-a-load-node}

Run 至少需要一个已初始化且处于 Idle 状态的 Load Node。请根据 SurgePilot 的启动方式
选择对应路径。

### 源码完整技术栈：注册 Demo Node

`make start-full-stack` 会启动 Compose 内部 SSH Node 并输出连接信息。在仓库根目录
验证 Host Key Fingerprint，并在本机读取生成的密码：

```sh
ssh-keygen -lf .surgepilot/demo-load-node/ssh_host_ed25519_key.pub -E sha256
cat .surgepilot/secrets/demo-load-node-password.secret
```

请将该密码视为 Secret，不要粘贴到 Issue、日志或源码文件中。

在 SurgePilot 中：

1. 打开 **Resources → Load Nodes**，选择 **Register Load Node**。
2. 保持 **Scope** 为 **Private**。
3. 输入 Host `demo-load-node`、Port `22` 和 SSH User `surgepilot`。
4. 选择 **Scan key**。将显示的 SHA-256 Fingerprint 与 `ssh-keygen` 输出对比，
   然后保留扫描到的 Key。
5. 选择 **Password** 认证并输入生成的密码。
6. 将 **Runner home** 留空以使用 API 默认值，然后选择 **Register Load Node**。
7. 返回 **Load Nodes**，对 `demo-load-node` 选择 **Initialize**，等待状态变为 **Idle**。

### Tagged Release：注册外部 Node

Tagged Release 默认禁用 Demo Node。请准备满足以下条件的 Linux 计算机：

- Ubuntu 24.04 或更高版本，或者 Debian 12 或更高版本。
- `x86_64`（`amd64`）或 `aarch64`（`arm64`）。
- SurgePilot API 可以通过 SSH 访问。
- 安装 `tar`、POSIX Shell、Java 11 或更高版本，以及 Python 3.12 或更高版本。

打开 **Resources → Load Nodes → Register Load Node**，输入 SSH 连接信息，扫描并
独立验证 Host Key Fingerprint，然后提供一种受支持的 Credential 类型。注册完成后，
选择 **Initialize** 并等待状态变为 **Idle**。该节点必须能访问你在 `surgepilot up`
期间确认的 API 和 InfluxDB Node-Facing URL。

## 第 4 步：创建 Scenario

Scenario 是可复用的有序请求流程。

1. 打开 **Scenarios**，选择 **Create Scenario**。
2. 将其命名为 `health-check`，并将 **Base URL expression** 设置为 `${base_url}`。
3. 打开新 Scenario，选择 **Add Step**。
4. 保持 Method 为 **GET**，输入安全的目标路径，例如 `/health`；如果目标的正确状态为
   `200`，请保留默认 Expected-Status Assertion。
5. 选择 **Save**。

选择 `local` Env Group 和一个 Idle Node 后，可以使用 **Debug Run** 进行聚焦验证。
Debug Run 只使用一个 Node，不会生成 Monitoring 数据。也可以直接继续创建低负载 Test Plan。

## 第 5 步：创建 Test Plan

Test Plan 将已保存的 Scenario 与 Env Group、负载设置、资源和可选 SLA Rule 组合起来。

1. 打开 **Test Plans**，选择 **Create Test Plan**。
2. 将其命名为 `health-check-low-load` 并创建。
3. 在 **Global Context** 下选择 `local` Env Group。
4. 在 **Resource Configuration** 下选择 **Manual selected nodes**，将 **Pool Type**
   设置为 **Private**，选择 Idle Node，然后选择 **Done**。
5. 在 **Scenario Orchestration** 下选择 **Add Scenario**，再选择 `health-check`。
6. 首次 Run 保持 **Concurrency / Node** 为 `1`、**Ramp-up** 为 `0`、**Hold-for** 为 `60`。
7. 可以按目标情况添加适当阈值的 SLA Rule。
8. 选择 **Save**。
9. 在 **Generated YAML Preview** 下选择 **Standard**，然后选择 **Preview YAML**。
   该 Preview 为只读，反映最新保存的 Test Plan Revision。

## 第 6 步：执行和评审

选择 **Run Now**。Run 执行期间，SurgePilot 会打开 Run Report。等待 Run 进入终态，
然后检查：

- **Verdict Summary**：Run 状态、Validity 和 SLA 结果。
- **KPI Summary** 和 **Final Stats Preview**：响应和错误指标。
- **Failure Diagnostics**：Run 未按预期完成时的诊断信息。
- **Snapshot Summary**：本次 Run 使用的不可变配置。
- **Artifacts**：可下载的日志和结果文件。
- **Nodes**：各 Node 的执行状态。

之后可以从 **Runs** 返回并选择 **View Report**。Report 记录保存的 Run Snapshot；
后续修改 Env Group、Scenario 或 Test Plan，不会重写这份历史记录。

*本中文译文由 AI 辅助完成；如与英文版存在差异，请以英文版为准。*
