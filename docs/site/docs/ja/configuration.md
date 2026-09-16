# デプロイ設定

SurgePilot はデプロイ設定をルートの `.env` ファイルに保存します。通常のユーザーが手作業で
このファイルを作成する必要はありません。公式の起動コマンドが初回実行時に作成し、Private Value を
生成して内容を検証し、以降の起動でも保持します。

## 正しい Template を選択する

Release と Source では Network、Runtime、Build の要件が異なるため、SurgePilot は意図的に
2 種類の Template を提供しています。

| デプロイ | リポジトリ内の Template | 通常のコマンド |
| --- | --- | --- |
| Tagged Release | `infra/release/.env.example`。インストール先の Release Directory では `.env.example` | `surgepilot up` または `./surgepilot up` |
| Source Checkout | ルート `.env.example` | `make start-full-stack` または `make start-preview` |

一方の Template をもう一方にコピーしないでください。Release Template では、最終的な Node-Facing
LAN Origin と Secure Cookie の意図が必要です。Source Template には Development Port、Source
Build Mirror、ローカルで生成する Runtime Input が含まれ、Release Deployment には属しません。

## `.env` の管理方法

1. `.env` がない場合、公式の起動処理が正しい Template をコピーし、Private Bootstrap Value を
   生成して、Owner-Only の Deployment State を書き込みます。
2. `.env` が既にある場合、起動処理はそれを正として扱い、既存値の上書き、Rotation、Repair を
   行いません。
3. Process Environment から明示的に渡した Bootstrap Value は、初回作成時だけ保存されます。
   以降の起動で競合する値を渡すと Fail-Closed になります。
4. Release の初回実行では Host と 2 つの Publish Port を確認し、最終的な API Origin と
   InfluxDB Node-Write Origin を保存します。以降の対話型起動で設定確認に **No** と回答した場合、
   更新できるのはこの 4 つの Network Field だけです。
5. Source Startup は Release の再設定フローを使用しません。Override が必要な場合は Source
   `.env` を意図的に編集してください。

手作業で変更した後は、Release では `surgepilot up`、実行中の Source Stack では
`make restart-full-stack` を実行します。どちらも Service を起動する前に実効設定を検証します。

::: danger 生成された Secret を安定して保持してください
`.env` を編集して Deployment Secret を Rotation しないでください。特に SSH Credential
Encryption Key を失うか変更すると、保存済み Load Node Credential を読み取れなくなります。
既存の Database Volume と Object Storage Volume も初期化時の Identity を保持します。
:::

## 設定リファレンスの読み方

- **変更不要**：生成値または Template 値が通常用途に適しています。
- **初回実行**：Release Prompt がデプロイ固有の値を設定します。
- **条件付き**：説明されたデプロイモードでのみ変更します。
- **高度**：運用上の理由と再起動計画がない限り変更しません。
- **管理対象**：公式 Startup または Runtime Command が値を設定します。通常用途では手動保存しません。
- **存在しない**：その Template では設定を公開していません。

## 起動と Network 設定

| 変数 | Release | Source | 設定方法と意味 |
| --- | --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `surgepilot` | `surgepilot` | **変更不要。** Docker Compose Resource Namespace。変更すると別の Stack と Named Volume が選択されます。 |
| `SURGEPILOT_HTTP_PORT` | `8080` | `8080` | **Release は初回実行、Source は条件付き。** Nginx が Web UI、API、Grafana Path 用に Publish する Host Port。空いている Port を使用します。 |
| `POSTGRES_HOST_PORT` | 存在しない | `5432` | **Source のみ、条件付き。** Source PostgreSQL Service が Publish する Host Port。Release PostgreSQL は Publish されません。 |
| `SURGEPILOT_API_HOST_PORT` | 存在しない | `8000` | **Source のみ、条件付き。** Source API Container の Direct Host Port。通常の Nginx Entry とは別です。 |
| `DEFAULT_WORKSPACE_NAME` | `Default Workspace` | `Default Workspace` | **条件付き。** 最初の Admin が初期 Workspace を作成するときの名前。既存 Workspace の名前は変更しません。 |
| `SURGEPILOT_NODE_API_BASE_URL` | 有効な LAN 例。初回実行で置換 | コメントされた例 | **Release は初回実行、Source の外部 Node は条件付き。** Load Node から到達可能な最終 API Origin。この値がない場合、Source Demo は Compose 内部 Origin を使用します。DB の System Setting は Application Fallback を上書きできます。 |
| `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT` | `8086` | `8086` | **Release は初回実行、Source は条件付き。** 認証済み Load Node が InfluxDB に書き込むための Host Port。HTTP Port とは異なる値が必要です。 |
| `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` | 有効な LAN 例。初回実行で置換 | コメントされた例 | **Release は初回実行、Source の外部 Node は条件付き。** Load Node から到達可能な最終 InfluxDB Origin。Node API Origin と同時に設定します。 |
| `SESSION_COOKIE_SECURE` | `false` | 存在しない | **条件付き。** Release HTTP Mode では `false`。Operator 管理の HTTPS Deployment では `true` にし、HTTPS Node API Origin を使用します。 |
| `SURGEPILOT_DEMO_LOAD_NODE_ENABLED` | `false` | `true` | **条件付き。** 任意の Compose 内部 Demo Load Node を有効化します。Release はデフォルトで無効、Source Full Stack は有効、Preview は `.env` を書き換えず強制的に無効化します。 |
| `SURGEPILOT_RUNTIME_ARCHITECTURES` | `amd64,arm64` | `auto` | **通常の起動では変更不要。** Load Node Runtime Asset を準備する Architecture。Release 初回実行では両方を保持し、Source の `auto` は Docker Daemon の Native Architecture を選択します。有効値は `auto`、`amd64`、`arm64`、`amd64,arm64` です。 |
| `APP_ENV` | 存在しない | `development` | **Source の Direct-Host Development のみ。** Application Environment Default を選択します。公式 Compose は固定値を設定します。 |
| `DATABASE_URL` | 存在しない | Local PostgreSQL URL | **Source の Direct-Host Development のみ。** `make dev-api`、`make dev-worker`、Compose 外 Migration が使用する Database Connection。公式 Compose は内部 URL を設定します。 |
| `MINIO_ENDPOINT` | 存在しない | `http://localhost:9000` | **Source の Direct-Host Development のみ。** Compose 外の API Process が使用する MinIO Endpoint。公式 Compose は内部 Endpoint を設定します。 |

## デプロイ Identity、Secret、MinIO

| 変数 | Template 値 | 設定方法と意味 |
| --- | --- | --- |
| `RUNNER_INTERNAL_TOKEN` | Placeholder を Random Token に置換 | **管理対象。** API と Runner 間で使用する共有内部認証情報。Private かつ安定した状態を維持します。 |
| `SSH_CREDENTIAL_ENCRYPTION_KEY` | Placeholder を Random Base64 Key に置換 | **管理対象。** 保存済み Load Node Credential 用の AES-256-GCM Key。Decode 後は正確に 32 Byte で、Database を再利用する間は変更できません。 |
| `MINIO_BUCKET` | `surgepilot` | **変更不要。** Dependency File と Run Artifact 用の Object Storage Bucket。 |
| `MINIO_ACCESS_KEY` | `minioadmin` | **同梱 Service では変更不要。** API 側 MinIO Access Identity。同梱 Deployment の MinIO Root User と一致する必要があります。 |
| `MINIO_SECRET_KEY` | Placeholder を Random Password に置換 | **管理対象。** API 側 MinIO Secret。同梱 Deployment の MinIO Root Password と一致する必要があります。 |
| `MINIO_ROOT_USER` | `minioadmin` | **同梱 Service では変更不要。** MinIO Initialization User。Access Key と一致させます。 |
| `MINIO_ROOT_PASSWORD` | MinIO Secret と同じ生成値 | **管理対象。** MinIO Initialization Password。API 側 Secret と一致させます。変更しても既存 MinIO Volume は再初期化されません。 |
| `MINIO_REGION` | コメント済み | **高度、Direct-Host のみ。** Endpoint から Region を判定できない場合に MinIO Client へ渡す任意 Region。公式 Compose はこの Override を渡しません。 |
| `MINIO_SECURE` | コメント済み、デフォルト `false` | **高度、Direct-Host のみ。** Scheme のない Direct-Host MinIO Endpoint で TLS を有効にします。明示的な `https` Endpoint は既に TLS を選択します。 |

## Monitoring Bootstrap とリンク

| 変数 | Template 値 | 設定方法と意味 |
| --- | --- | --- |
| `SURGEPILOT_MONITORING_INFLUXDB_USERNAME` | `surgepilot` | **通常の初回実行では変更不要。** InfluxDB Initialization Username。編集しても既存 Volume は再初期化されません。 |
| `SURGEPILOT_MONITORING_INFLUXDB_PASSWORD` | Placeholder を Random Password に置換 | **管理対象。** InfluxDB Initialization Password。Setup CLI が Flag として解釈するため、`-` で始めることはできません。 |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST` | 例の Path を Private Generated File に置換 | **管理対象。** InfluxDB Token Secret として Mount する Host Path。公式 Startup が Private Token File を作成し、選択した Layout に正しい Path を書き込みます。 |
| `SURGEPILOT_MONITORING_INFLUXDB_ORG` | `surgepilot` | **変更不要。** Setup、Backend Listener、Monitoring Link で使用する InfluxDB Organization。 |
| `SURGEPILOT_MONITORING_INFLUXDB_BUCKET` | `jmeter` | **変更不要。** Standard Run Metric を受信する InfluxDB Bucket。 |
| `SURGEPILOT_GRAFANA_ADMIN_USER` | `admin` | **条件付き。** Grafana Bootstrap Admin Username。別名が必要な場合は Grafana Volume 初期化前に設定します。 |
| `SURGEPILOT_GRAFANA_ROOT_URL` | コメント済み、Grafana Subpath Expression | **高度。** `/grafana/` 配下で提供するときの Grafana Server Root URL。Template 値は同梱 Proxy Layout に一致します。 |
| `SURGEPILOT_MONITORING_DASHBOARD_UID` | コメント済み、`surgepilot-jmeter-13644` | **高度。** Provisioning 済み Read-Only JMeter Dashboard Link の UID。対応する Grafana Provisioning と同時にのみ変更します。 |
| `SURGEPILOT_MONITORING_DASHBOARD_SLUG` | コメント済み、`jmeter-load-test` | **高度。** Provisioning 済み Dashboard Link の Slug。対応する Grafana Provisioning と同時にのみ変更します。 |
| `SURGEPILOT_MONITORING_ENABLED` | コメント済み、Direct-Host API のデフォルト `false` | **Direct-Host のみ。** 公式 Full-Stack Compose は Monitoring を明示的に有効化するため、この `.env` Override で同梱 Monitoring は無効になりません。 |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED` | コメント済み、Direct-Host API のデフォルト `false` | **Direct-Host のみ。** 直接起動した API に、Monitoring Token State が外部設定済みかを伝えます。公式 Compose は正しい値を設定します。 |
| `SURGEPILOT_MONITORING_GRAFANA_BASE_PATH` | コメント済み、`/grafana` | **Direct-Host のみ。** 生成される Grafana Link の Base Path。公式 Compose は同梱 Path を `/grafana` に固定します。 |
| `SURGEPILOT_MONITORING_TIME_PADDING_SECONDS` | コメント済み、`60` | **高度。** Monitoring Link 生成時に Run Time Range の前後へ追加する秒数。 |

InfluxDB Initialization Username、Password、Organization、Bucket は `-` で始められません。
InfluxDB Setup CLI が Flag として解釈します。

## Source Runtime と Image Build 設定

これらは Source Template だけに存在します。Tagged Release は Source から Build せず、
Pinned Application Image と検証済み Runtime Asset を Pull します。

| 変数 | Template 値 | 設定方法と意味 |
| --- | --- | --- |
| `LOAD_NODE_RUNTIME_VERSION` | コメント済み | **管理対象。** 公式 Runtime Builder が生成済み `runtime.env` State に書き込む Runtime Version。 |
| `LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR` | コメント済みの Absolute Path 例 | **管理対象。** Generated Runtime State に書き込み、API Service へ Read-Only Mount する Host Directory。 |
| `SURGEPILOT_SKIP_RUNTIME_PREFLIGHT` | コメント済み、`1` | **高度な手動/Debug のみ。** Source Full-Stack Startup の Runtime 準備を省略します。Deployment Bootstrap は省略せず、Load Node や Run の準備完了も保証しません。 |
| `RUNTIME_JMETER_SHA256` | コメント済み | **高度。** Source Runtime Builder の JMeter Download に渡す任意の Expected Checksum。 |
| `RUNTIME_CASUTG_SHA256` | コメント済み | **高度。** Concurrency Thread Group Plugin 用の任意 Expected Checksum。 |
| `RUNTIME_JSON_SHA256` | コメント済み | **高度。** JSONPath Plugin 用の任意 Expected Checksum。 |
| `RUNTIME_TST_SHA256` | コメント済み | **高度。** Throughput Shaping Timer Plugin 用の任意 Expected Checksum。 |
| `RUNTIME_RANDOM_CSV_SHA256` | コメント済み | **高度。** Random CSV Data Set Plugin 用の任意 Expected Checksum。 |
| `RUNTIME_INFLUXDB2_LISTENER_SHA256` | コメント済み | **高度。** InfluxDB2 Listener Plugin 用の任意 Expected Checksum。 |
| `SURGEPILOT_PIP_INDEX_URL` | コメント済みの Mirror 例 | **条件付き。** Source Docker Build と Runtime Builder が使用する Python Package Index。未設定では Upstream Default を使用します。 |
| `SURGEPILOT_NPM_REGISTRY` | コメント済みの Mirror 例 | **条件付き。** Source Web Image Build が使用する npm Registry。未設定では Upstream Default を使用します。 |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR` | コメント済みの無効な例 | **条件付き。** Source Docker Build だけで使用する Ubuntu Package Mirror。有効化前に実在する Mirror へ置換します。 |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR` | コメント済みの無効な例 | **条件付き。** Source Docker Build だけで使用する Ubuntu Security Mirror。 |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR` | コメント済みの無効な例 | **条件付き。** Source Docker Build だけで使用する Debian Package Mirror。 |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR` | コメント済みの無効な例 | **条件付き。** Source Docker Build だけで使用する Debian Security Mirror。 |
| `VITE_API_BASE_URL` | コメント済みの Direct API 例 | **高度、Source Build のみ。** Web Client の Build-Time Seed。同梱 Web Runtime は Same-Origin `/api` を使用するため、通常の Deployment では未設定にします。 |

## DB-Backed System Setting の Fallback

次の `.env` Value は、対応する Database System Setting がない場合だけ使用されます。通常の
Policy 変更は `.env` を編集せず、**Admin → System Settings** を使用してください。Environment
Fallback の変更を読み込むには Deployment の再起動が必要で、既存 DB Value が引き続き優先されます。

| 変数 | Fallback | 意味 |
| --- | --- | --- |
| `ALLOW_SIGNUP` | `true` | 最初の Admin 以降の User が登録できるか。Setup が未完了の場合、最初の Admin Bootstrap は利用できます。 |
| `DEPENDENCY_FILE_MAX_BYTES` | `104857600` | Dependency File Upload の最大 Byte 数。 |
| `DEPENDENCY_FILE_ALLOWED_EXTENSIONS` | 空 | Comma-Separated Allowlist。空では Extension Allowlist を適用しませんが、Filename Safety Check は継続します。 |
| `DEPENDENCY_FILE_PREVIEW_MAX_BYTES` | `65536` | Single-File Text Preview が返す最大 Byte 数。 |
| `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS` | Template Extension List | Text Preview として表示しない Comma-Separated Extension。 |
| `SURGEPILOT_MAX_SCENARIO_ITEMS_PER_TEST_PLAN` | `20` | 1 つの Test Plan で有効にできる Scenario Item の上限。 |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT` | `1000` | 明示的な High-Concurrency Confirmation が必要になる Per-Node Concurrency Threshold。 |
| `SURGEPILOT_MAX_RUN_DURATION_SECONDS` | `86400` | 設定可能な Run Duration の上限。 |
| `SURGEPILOT_MAX_RAMP_UP_SECONDS` | `86400` | Ramp-Up Duration の上限。実効 Run-Duration Limit を超えることはできません。 |
| `SURGEPILOT_MAX_DELAY_SECONDS` | `86400` | 設定可能な Start Delay の上限。 |
| `SURGEPILOT_MAX_ITERATIONS` | `1000000` | Iteration-Based Load Model の Iteration 上限。 |
| `SURGEPILOT_MAX_TARGET_RPS` | `100000` | Load-Model Validation が受け入れる Target RPS の上限。設定上限であり Performance Claim ではありません。 |
| `SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN` | `5` | Standard Test Plan で有効にできる SLA Rule の上限。 |
| `SURGEPILOT_JMETER_MEMORY_XMX` | `4G` | Execution Config に書き込む JMeter Maximum Heap。正の整数に `K`、`M`、`G` のいずれかを付けます。 |

## 高度な運用 Guardrail

次の値には Application と Compose の Default があります。測定結果に基づく理由がない限り、
コメントのままにしてください。変更後は再起動が必要です。

### Load Node の初期化

| 変数 | Default | 意味 |
| --- | --- | --- |
| `LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS` | `30` | Load Node Initialization 中の個別 Command Timeout。 |
| `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS` | `120` | Load Node への Runtime Install Timeout。 |
| `LOAD_NODE_DEFAULT_RUNNER_HOME` | `/opt/surgepilot/runner` | Load Node が別の Path を指定しない場合の Default Remote Runner Home。 |
| `LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS` | `15` | Load Node Operation の SSH Connection Timeout。 |
| `LOAD_NODE_INIT_TIMEOUT_SECONDS` | `120` | Stale Initialization Attempt と Initialization State に残った Node を復旧する Age Threshold。 |
| `LOAD_NODE_INIT_LOG_TAIL_BYTES` | `65536` | Status と Failure Report 用に保持する Initialization Log Tail の最大 Byte 数。 |
| `LOAD_NODE_GENERATED_KEY_TYPE` | `ed25519` | SurgePilot が Load Node Keypair を生成するときの SSH Key Type。 |

### Run Control と Artifact

| 変数 | Default | 意味 |
| --- | --- | --- |
| `SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS` | `60` | Runner Accept 後に Execution Start を待つ最大時間、および Running 後の Heartbeat 最大間隔。 |
| `SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS` | `120` | Runner がリモート要求の Allocation を Accept するまでの最大待機時間。 |
| `SURGEPILOT_RUN_STOP_GRACE_SECONDS` | `60` | Force-Kill Handling 前に通常停止を許可する Grace Period。 |
| `SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS` | `30` | Force-Kill Control で使用する SSH Timeout。 |
| `SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS` | `30` | Persisted Runner Callback Record の Retention Period。 |
| `SURGEPILOT_RUN_CONTROL_STALE_SECONDS` | `120` | Claim 済み Run-Control Work を Recovery 対象の Stale とみなす時間。 |
| `SURGEPILOT_NODE_COOLDOWN_SECONDS` | `300` | Force-Kill 後、その Load Node を再 Allocation できるまでの Cooldown Period。 |
| `SURGEPILOT_RUN_ARTIFACT_MAX_BYTES` | `209715200` | 通常 Run Artifact の最大許容 Size。 |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES` | `1048576` | Run が Terminal State に到達した後に受け入れる Artifact の最大 Size。 |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS` | `300` | Terminal State 到達後、制限付き Late Artifact を受け入れる時間枠。 |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT` | `10000` | Per-Node Concurrency の Hard Ceiling。Confirmation で回避できず、DB から編集できません。 |

### API Catalog と Debug HTTP Trace

| 変数 | Default | 意味 |
| --- | --- | --- |
| `SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES` | `10485760` | Upload 可能な API Catalog Specification の最大 Size。 |
| `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS` | `100` | 1 回の Debug HTTP Trace で保持する Request Record の上限。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES` | `65536` | Trace Record ごとに Inline 保持する Request/Response Body の最大 Byte 数。 |
| `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES` | `10485760` | Parsing 対象として受け入れる Debug HTTP Trace Artifact の最大 Size。 |
| `SURGEPILOT_DEBUG_TRACE_RECORD_MAX_BYTES` | `131072` | 1 つの Trace Record の最大 Encoded Size。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_MAX_BYTES` | `5242880` | 個別保存する Trace Body Blob 1 つの最大 Size。 |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES` | `20971520` | 1 つの Trace Artifact で個別保存する Trace Body の合計最大 Byte 数。 |

## 手動で編集する前に

1. 値が Release Template と Source Template のどちらに属するか確認します。
2. **管理対象**と記載された設定は変更しません。
3. `.env` の Ownership と Owner-Only Permission を維持します。
4. `.env` や生成された Secret File を Commit しないでください。
5. Release Network を変更する場合は、直接編集より `surgepilot up` の確認フローを優先します。
6. 変更後は公式起動コマンドを実行し、Service 起動前に実効設定 Summary を確認します。

起動動作と対応モードについては、[起動モード](./startup-modes.md)へ進んでください。
プロダクト用語については、[用語と FAQ](./faq.md)を参照してください。

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
