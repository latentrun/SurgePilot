# 起動モード

SurgePilot には 1 つの Tagged Release Mode と 2 つの Source Checkout Entry があります。
最も速く起動するコマンドではなく、確認したい内容に合わせて選択してください。

| モード | 用途 | Runtime | Demo Load Node | アプリケーションの Source Build |
| --- | --- | --- | --- | --- |
| Tagged Release | セルフホスト型デプロイ | 新規デプロイで検証済みの `amd64` と `arm64` Asset をダウンロード | デフォルトで無効 | なし。Digest-Pinned Image を Pull |
| Source Full Stack | 開発と完全なローカル実行経路 | Native Linux Runtime を Build または再利用 | 起動後、ユーザーが登録・初期化 | あり |
| Source Preview | ログイン、UI、Control Plane、Monitoring のレビュー | 準備しない | 無効 | あり |

すべてのモードで永続的なデプロイ状態を使用しますが、Release と Source Checkout では
`.env` Template が異なります。各 Field と初回動作については、
[デプロイ設定](./configuration.md)を参照してください。

## Tagged Release

Release をインストールし、ユーザー単位の Launcher を使用します。

```sh
surgepilot up
surgepilot status
surgepilot logs
surgepilot down
```

Version 付き Release Archive を手動でダウンロードして検証した場合は、展開先ディレクトリで
`./surgepilot up`、`./surgepilot status`、`./surgepilot logs`、
`./surgepilot down` を使用して同じ Lifecycle を操作します。

Release は Web、API、api-worker、PostgreSQL、MinIO、Nginx、InfluxDB、Grafana を
起動します。デプロイホストで Application Source を Build したり Runtime を Compile したりは
しません。Load Node と Runtime は Linux 専用です。macOS 対応とは、Container 化された
Control Plane を Docker Desktop で実行できることを意味します。

有効な `up` は、Runtime を取得する前に、実際の Web/API Endpoint、InfluxDB Node-Write
Endpoint、Runtime Architecture、Demo State を表示します。既存の有効な `.env` は、Yes と
回答するか Enter を押すと書き換えずに受け入れられます。非対話環境で `.env` がない場合は
Fail-Closed となり、Automation が完全な Owner-Only `.env` を事前に用意する必要があります。

生成される Direct-LAN 設定は HTTP を使用し、信頼できる Network を対象としています。
Internet-Facing Deployment では、Operator が管理する HTTPS Reverse Proxy、外部から到達可能な
最終 Node-Facing Origin、`SESSION_COOKIE_SECURE=true` が必要です。この高度な設定は `.env`
を明示的に編集します。初回 Prompt は TLS を設定しません。

## Source Full Stack

公式の完全な Source Entry を使用します。

```sh
make start-full-stack
```

初回利用時に、ルート `.env` と Private Local State を作成します。続いて Native Architecture の
Runtime を準備し、完全な Compose Config を検証して Application Image を Build し、Monitoring と
Compose 内部の Demo Load Node を起動します。デフォルトの Web URL は
`http://localhost:8080` です。

Run で選択できるようにするには、Demo Node を SurgePilot に登録して初期化する必要があります。
[Load Node の準備](./first-run.md#prepare-a-load-node)を参照してください。

```sh
make restart-full-stack
make stop-full-stack
```

どちらの Lifecycle Command もルート `.env`、Private State、Compose Volume を保持します。
Restart Preflight は、実行中の Stack を停止する前に完了します。

## Source Preview {#source-preview}

実行リソースを準備せずに、ログインページ、プロダクト UI、Control Plane の動作、Monitoring を
確認する場合にだけ Preview を使用します。

```sh
make start-preview
```

Preview は Web、API、api-worker、PostgreSQL、MinIO、Nginx、InfluxDB、Grafana を起動します。
Runtime の準備を意図的に省略し、Demo Load Node を無効にします。Setup Status が
`not_configured` と表示される場合があります。Load Node の初期化や Run の実行準備は保証されません。

`http://localhost:8080` を開きます。Volume を削除せず Preview を停止するには、次を実行します。

```sh
make stop-preview
```

Preview と Source Full Stack は、同じ安全なルートデプロイ状態を使用します。完全な実行経路が
必要になったら、`make start-full-stack` に切り替えてください。

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
