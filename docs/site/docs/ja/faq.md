# 用語集と FAQ

## 基本用語

### Control plane

設定の保存と処理の調整を担う Web、API、api-worker、PostgreSQL、MinIO、Nginx、Monitoring の各サービスです。Control plane 自体が負荷を生成することはありません。

### Runtime

Load Node にインストールされる、バージョン管理された Linux 実行 bundle です。ソースのフルスタック起動では、ホストと同じアーキテクチャの Runtime をビルドまたは再利用します。タグ付きリリースでは、選択したビルド済み Runtime asset をダウンロードして検証します。

### Load Node

独立した SurgePilot Runner と負荷テスト engine を実行する Linux マシンです。Run で選択するには、node が登録・初期化済みで、接続可能かつ **Idle** 状態である必要があります。

### Env Group

再利用可能な環境変数のセットです。通常の値は保存後も読み取れます。Secret の値はサインイン済みの UI から登録でき、以降はマスクされた metadata だけが返されます。製品上で元の値を表示することはできません。

### Scenario

HTTP Step を順序どおりに並べ、リクエストの詳細と構造化されたグローバル設定をまとめた再利用可能なフローです。Scenario は「何を呼び出すか」を定義し、負荷の大きさは定義しません。

### Test Plan

Scenario、任意の Env Group、リソースの選択、Scenario ごとの負荷設定、任意の SLA ルールを組み合わせて保存した実行定義です。

### Debug Run と Standard Run

Debug Run は、1 台の node で集中的に検証するための実行方法です。Standard Run は Test Plan のリソース設定と負荷設定を使用し、SLA ルールを評価して、有効になっているメトリクスを Monitoring に送信できます。

### Run と Run Report

Run は、保存済みの source revision を 1 回実行したものです。Run Report では、最終 verdict、メトリクス、immutable snapshot、診断情報、artifact、node ごとの状態を確認できます。

### Preview

「Preview」には、異なる 2 つの意味があります。

- **Source preview** は `make start-preview` で起動する control plane のモードです。Runtime、Load Node、Run の実行準備が整うことは保証されません。
- **Generated YAML Preview** は、最後に保存した Test Plan revision に対して API が生成した設定を読み取り専用で表示する機能です。Run は開始されません。

SurgePilot に、Scenario 実行専用の Preview はありません。

## よくある質問

### どの起動方法を選べばよいですか？

タグ付きの self-hosted リリースでは `surgepilot up` を使用します。ソースから開発する場合や、ソースの完全な実行経路を確認する場合は `make start-full-stack` を使用してください。`make start-preview` は、Run の実行準備を必要とせず、ログイン、UI、control plane、Monitoring だけを確認する場合に使用します。

### 起動前に `.env` を作成または編集する必要がありますか？

通常の対話型起動では必要ありません。`.env` が存在しない場合、`surgepilot up`、`make start-full-stack`、`make start-preview` が安全なデプロイ状態を作成します。リリースの初回起動では LAN host と port を入力し、ソース起動ではソース向けのデフォルト値を使用します。既存の `.env` が正とされ、自動的に上書きまたは修復されることはありません。手動で変更する前に、[デプロイ設定](./configuration.md)を参照してください。

### Source Preview で Setup Status が `not_configured` になるのはなぜですか？

Source Preview は意図的に Runtime の準備を省略し、Demo Load Node を無効にします。そのため、Runtime check が `not_configured` になるのは正常です。Load Node の初期化や Run の実行が必要な場合は、ソースのフルスタックを起動してください。

### Asset は作成できるのに Run を開始できないのはなぜですか？

Env Group、Scenario、Test Plan は、実行リソースがなくても作成できます。Run の開始には、保存済みで実行可能な Test Plan と、条件に合う初期化済みかつ現在 **Idle** 状態の Load Node も必要です。

### ソースのフルスタックは Demo Load Node を自動登録しますか？

いいえ。Demo SSH container の起動と認証情報の準備は行いますが、Admin が **Load Nodes** から登録し、ホストキーを検証して初期化する必要があります。

### タグ付きリリースに Demo Load Node は含まれますか？

リリース bundle には任意で使用できる Demo profile が含まれますが、通常のリリース起動では無効です。実行するには外部の Linux Load Node を登録してください。

### Load Node から SurgePilot への接続に `localhost` を使えますか？

別のマシンまたは別の container で node を動かす場合は使えません。その環境の `localhost` は node 自身を指します。API と InfluxDB の node 向け URL には、Load Node から到達できるアドレスを設定してください。リリースの初回起動時に、このアドレスの入力を求められます。

### `down` を実行すると設定や結果も削除されますか？

いいえ。`surgepilot down`、`make stop-full-stack`、`make stop-preview` は Compose service を停止しますが、デプロイ用の `.env` や named volume は削除しません。

### LAN 内での直接 HTTP 接続をインターネット公開に使えますか？

いいえ。タグ付きリリースの対話型セットアップが構成するのは、信頼できる LAN 向けの HTTP 接続です。インターネットに公開する場合は、運用者が管理する HTTPS reverse proxy、確定した node 向け origin、安全な session cookie、firewall policy、一般的な本番運用上の対策が必要です。

### macOS を Load Node として使用できますか？

いいえ。macOS では Docker Desktop を使って container 化された control plane を動かせますが、Load Node と Runtime は Linux のみをサポートします。

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
