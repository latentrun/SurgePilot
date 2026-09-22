# クイックスタート

Source Checkout なしで SurgePilot を実行する場合は Tagged Release を使用します。
SurgePilot 自体を開発する場合は、ソースコードから起動します。

## Tagged Release のインストール

### 前提条件

- Docker Engine 26 以降をインストールした Linux ホスト、または Docker
  Desktop 26 以降をインストールした macOS ホスト。
- Docker Compose 2.27 以降（旧式の `docker-compose` ではなく、
  `docker compose` コマンドを使用）。
- `curl`、`tar` を含む標準的なホストツール。
- 最初の `up` を実行するための対話型ターミナル。

Installer は Docker のインストールや設定を行いません。

### ステップ 1：インストールと起動

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

Installer は `sudo` を使用せず、Shell の起動ファイルも変更しません。選択された Release は
`${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot` にインストールされ、Launcher は
`$HOME/.local/bin/surgepilot` に作成されます。

このディレクトリが `PATH` に含まれていない場合は、Installer が表示する絶対パスのコマンドを
使用するか、現在の Shell だけで有効にします。

```sh
export PATH="$HOME/.local/bin:$PATH"
surgepilot up
```

### ステップ 2：初回設定の確認

新規デプロイでは、`surgepilot up` が次の項目を確認します。

1. ブラウザと外部 Load Node が使用する Hostname または IP Address。
2. SurgePilot Web と API トラフィック用の HTTP Port。
3. Load Node が Monitoring Data を書き込む InfluxDB Port。

他のマシンや Load Node から到達できるアドレスを使用してください。ローカル評価では
`localhost` または `127.0.0.1` を入力できますが、保存される Node-Facing URL は別の
マシンから利用できません。Docker は選択した Port を引き続き Host Interface 上に Publish
します。Loopback のみに公開する必要がある場合は、ホストの Firewall を使用してください。

コマンドは正規化済みの非 Secret 設定を表示し、`Use this configuration? [Y/n]` と確認します。
Enter を押すと受け入れます。新しい Release Deployment では両方の Linux Runtime Architecture
`amd64,arm64` が選択され、Demo Load Node はデフォルトで無効です。

続いて、一致する Runtime Asset を検証してダウンロードし、Immutable Application Image を Pull、
Stack を起動して Web URL を表示します。生成される `.env`、Release Network Field、Optional
Setting については、[デプロイ設定](./configuration.md)を参照してください。

### ステップ 3：デプロイの確認

```sh
surgepilot status
surgepilot logs
```

`surgepilot up` が表示した Web URL を開き、[初回実行](./first-run.md)へ進みます。

Volume と `.env` を削除せずに Stack を停止するには、次を実行します。

```sh
surgepilot down
```

### インストール済み Release のアップグレード

PostgreSQL、MinIO、その他の永続 Volume をバックアップし、実行中の Run と Load Node の
初期化が完了してから、同じ 2 つのコマンドを再度実行します。

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

Installer は、同じ Major Version に属する明示的な新しい Release を検証して準備します。
サポート対象の処理が実行中の場合、`surgepilot up` は Migration を拒否します。Target Database
Migration の開始後は、同じ Target を再試行して Recovery します。Database の自動 Downgrade や
Rollback はありません。Control Plane の Upgrade が成功した後も記録済み Runtime が古いままの
Load Node は、必要に応じて明示的に再初期化してください。

## ソースコードから起動する

ソースコードからの起動には Git、GNU Make または互換実装、POSIX Shell、Perl、`curl`、
`tar`/gzip、SHA-256 検証ツール、Docker、Docker Compose が必要です。
リポジトリのルートで次を実行します。

```sh
make setup
make start-full-stack
```

Make は固定バージョンの mise Bootstrap をダウンロードして検証し、リポジトリが選択した
Python 3.12、Node.js 22、pnpm、uv を分離された Contributor Namespace にインストールします。
Global Runtime Version や Shell Startup File は変更しません。オフラインかつ非変更の診断には
`make toolchain-check`、Managed State の明示的な修復には `make toolchain-install` を使用します。

ルートに `.env` が存在しない場合、`make start-full-stack` は安全なローカルデプロイ状態を
作成し、Native Linux Architecture の Load Node Runtime を Build または再利用します。その後、
Control Plane、Monitoring、Compose 内部の Demo Load Node を起動します。
`http://localhost:8080` を開いてください。

Source Template と Release Template は意図的に異なります。Source `.env` を変更する前に、
[デプロイ設定](./configuration.md)を確認してください。

Demo Node は起動していますが、まだプロダクトデータベースには登録されていません。Run を開始する前に、
[Load Node の準備](./first-run.md#prepare-a-load-node)にある Source Demo の手順を実行してください。

以降の Lifecycle 操作には、次のコマンドを使用します。

```sh
make restart-full-stack
make stop-full-stack
```

実行準備を必要とせず UI だけをレビューする場合は、
[Source Preview](./startup-modes.md#source-preview)を使用してください。

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
