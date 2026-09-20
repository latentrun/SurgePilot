# SurgePilot

**AI Agent が 100% 構築した、実在する分散システム。**

![100% AI-Built](https://img.shields.io/badge/original%20baseline-100%25%20AI--authored-8b5cf6) ![Self-Hosted](https://img.shields.io/badge/deploy-self--hosted-06b6d4) ![Contract-First](https://img.shields.io/badge/API-contract--first-22d3ee) ![Coverage Gate](https://img.shields.io/badge/coverage%20gate-%E2%89%A590%25-16a34a) ![License](https://img.shields.io/badge/license-MIT-22c55e)

[English](README.md) | [简体中文](README.zh-CN.md) | 日本語

**[★ GitHub で Star](https://github.com/latentrun/SurgePilot)** · [公開サイト](https://latentrun.github.io/SurgePilot/) · [ドキュメント](https://latentrun.github.io/SurgePilot/docs/ja/) · [Releases](https://github.com/latentrun/SurgePilot/releases)

SurgePilot はセルフホスト型の分散 API 負荷テストプラットフォームであり、AI Agent が要件と
ガバナンスからアーキテクチャ、実装、検証、リリースまで実在するシステムを進められるかを確認
できる Agentic Engineering の実験でもあります。API とビジネスフローを再利用可能な
**設計 → オーケストレーション → 実行 → レポート**のループにまとめます。

最初の公開ベースラインは、人間の指導のもと、AI Agent がエンドツーエンドで構築しました。
人間はプロダクトの方向性を定め、要件に対するフィードバックを行い、プロダクトを実際に使い、
成果を確認して受け入れました。AI Agent はプロダクトを設計・実装し、テスト、検証、デプロイ、
リリースまで担いました。

![AI 支援によるテスト設計から分散負荷実行と結果分析までの SurgePilot ワークフロー](.github/assets/surgepilot-overview.png)

## ハイライト

- ⚡ **1 つのコマンドで SurgePilot をセルフホスト。** `surgepilot up` で Web、API、
  api-worker、PostgreSQL、MinIO、Nginx、Grafana + InfluxDB を起動できます。
  ソースのチェックアウトは不要です。
- 🤖 **エンドツーエンドで 100% AI により構築。** PRD → SDD → ADR → Slice →
  Contract → テスト → デプロイというライフサイクル全体が AI によって作成され、すべて
  このリポジトリに保存されています。
- 🧭 **勘に頼るコーディングではなく、ガバナンスに基づく開発。** `AGENTS.md`、Scope Gate、
  ADR、Contract-First ルールにより、すべての変更範囲が明確になり、レビュー可能な状態に保たれます。
- 🔒 **明確なセキュリティ境界。** Workspace 分離、ロールベースの管理権限、
  暗号化された Load Node の認証情報、スコープが制限された Public REST API を備えています。
- 🌐 **実際の分散実行。** API が SSH 経由でリモート Load Node 上の独立した Runner を制御し、
  複数ノードの結果を集約して、メトリクスを InfluxDB へストリーミングします。
- 🧩 **AI ネイティブなインフラストラクチャ。** ガバナンスされた AI Skill パッケージにより、
  Claude や Codex などの Agent が負荷テストを直接操作できます。PAT 認証、Workspace スコープ、
  書き込み操作の必須確認に対応しています。
- ✅ **検証は必須。** `make verify` が lint、テスト、90% 以上のカバレッジゲート、Contract の
  最新性を検証し、実際の SSH を使用した E2E プロファイルがその品質を支えます。

## SurgePilot でできること

パフォーマンスチームは、同じような課題に繰り返し直面します。負荷テストスクリプトが使い捨てに
なりやすく再利用しにくい、環境ごとに設定をやり直す必要がある、1 回のテストのために複数の
負荷生成マシンを手動で接続しなければならない、結果が分散して目標に対する成否を判断しにくい、
といった問題です。

SurgePilot は、これらを再利用可能で、オーケストレーションされ、追跡可能な 1 つのループに
まとめます。API やビジネスフローを、一度設計すれば複数環境で繰り返し使えるテストアセットに変換し、
負荷モデルと合否基準でオーケストレーションし、複数の Load Node で分散実行します。最後に、判定、
主要メトリクス、Artifacts を集約した信頼できるレポートを提供します。これにより、低レベルな
実行エンジンの設定ではなく、*何をテストし、結果がどうだったか*に集中できます。

すべてを UI から手作業で操作する必要もありません。SurgePilot は AI Agent と連携できます。
後述する同梱の AI Skill を Claude や Codex などのツールと組み合わせることで、ガバナンスと
権限チェックが適用された経路から、会話形式でテストの起動、実行、確認を行えます。

## 100% AI による構築

SurgePilot は、単発のコード生成とは対極にある、ガバナンスされた AI 駆動開発の実例です。
システム全体は、明示的かつ監査可能なライフサイクルに沿って構築されました。

作者範囲の詳細は [AI 著者情報](AI-AUTHORSHIP.md) を参照してください。

| ステージ | AI が作成したもの | 使用した AI ツール | リポジトリ内の根拠 |
|---|---|---|---|
| 1. プロダクト | プロダクト要件 | GPT · Gemini | [`docs/prd`](docs/prd/PRD.md) |
| 2. UI/UX | フロントエンドのインターフェースと体験 | Claude · Gemini · Google Stitch | [`apps/web`](apps/web) |
| 3. システム設計 | SDD、Scope Gate、ADR、承認済み Slice | GPT · Claude | [`docs/sdd`](docs/sdd/README.md) · [`adr`](docs/sdd/adr/README.md) · [`slices`](docs/sdd/slices/P2-README.md) |
| 4. 実装 | アプリケーションコードと API Contract | GPT | [`packages/contracts`](packages/contracts) · [`apps`](apps) |
| 5. 検証 | Review 修正、テスト、ゲート | GPT · Claude | [`Makefile`](Makefile) · [テスト戦略](docs/sdd/09-testing-and-acceptance-strategy.md) |
| 6. リリース | 起動、デプロイ、リリース資産 | GPT | [`infra/release`](infra/release) · [Workflows](.github/workflows) |

ここにブラックボックスはありません。上記の各ステージは、実際の成果物へリンクしています。
[`AGENTS.md`](AGENTS.md) は、このプロセスを再現可能にした機械可読な Contract です。
コードに触れる前に関連するスコープを読み込み、利用側より先に Contract を更新し、API/Runner
境界を守り、検証ゲートを通過することを定めています。その結果生まれたのは、ガバナンスのない
生成ファイルの寄せ集めではなく、検証、再現、拡張が可能な分散システムです。

## アーキテクチャ

SurgePilot は**分散型のマルチサービスシステム**です。分離された Web フロントエンドと API
バックエンド、独立したバックグラウンド Worker、そして複数のリモートノードに配置された Runner が、
並列に負荷を生成し、文書化されたプロトコルを通じて結果を返します。（ソースコードは 1 つの
monorepo にありますが、実行時は Monolith ではありません。）各サービス間の明確で厳密な境界が、
セキュリティ、信頼性、独立したスケーリングの基盤です。

![SurgePilot システムアーキテクチャ](docs/site/public/surgepilot-architecture.jpg)

## 主な機能

社内 Platform Team が実際に評価する観点ごとにまとめています。すべての項目は、リポジトリに
チェックインされた Route、生成済み Contract、テストによって裏付けられています。機能ごとの
利用方法はこの概要ではなく、プロダクトドキュメントで説明します。

- **チーム分離とアクセス制御。** 複数チームの Workspace、Workspace ごとのデータ分離、
  User Management、バックエンドで強制される admin/user Role に対応しています。
- **認証情報と Secret のセキュリティ。** Load Node の認証情報は暗号化して保存され、
  書き込み専用で値を返しません。Env Group Variable は `plain | secret` 型とマスク表示に対応し、
  機密性の高い操作は監査イベントとして記録されます。
- **コアテストワークフロー。** Visual Scenario の設計、cURL Import、OpenAPI Operation からの
  Step Draft 生成、Test Plan のオーケストレーション、制御された Run 実行、Run Report、
  Artifacts、Debug HTTP Trace に対応しています。
- **スケールと Observability。** 複数ノードでの分散 Run 実行と結果集約に加え、各ノードからの
  Metrics Streaming によって更新される読み取り専用 Monitoring（Grafana + InfluxDB）を提供します。
- **自動化と Integration。** PAT 認証とスコープ制限を備えた Public REST API、生成済み Public
  OpenAPI Artifact、API Catalog、Agent 駆動操作のためのガバナンスされた AI Skill Package を
  提供します。
- **セルフホスト運用。** 1 コマンドでのフルスタック起動、Contract-First Architecture、
  90% 以上のカバレッジ検証ゲートを備えています。

利用可能な機能は、Active な Slice SDD と ADR によって管理されます。このリポジトリでは、
Scheduling、汎用 Secret Manager Integration、編集可能な Raw Engine Config、SSO、Kubernetes
など、非 Active の Roadmap 項目を利用可能な機能として提示することは**ありません**。

## AI-Native：AI Agent から SurgePilot を操作する

SurgePilot は AI Agent を後付け機能ではなく、第一級の Operator として扱います。Portable な
`SKILL.md` 形式で、ガバナンスされた **Public API AI Skill Package** を提供します。これにより、
**Claude** や **Codex** などの Coding Agent は HTTP Call を推測することなく、安全で
Contract に拘束された経路から Platform を操作できます。

**ワンクリックで取得：**サインイン済みのユーザーは、アプリ内の **Help → AI Agents** Tab を
開き、すぐに使える Skill Archive（`surgepilot-public-api-skill.zip`）を UI から直接
ダウンロードできます。リポジトリの Checkout や Build は不要です。解凍した Folder を Agent に
指定すれば、SurgePilot を操作できるようになります。

この Skill は、スコープが制限された Public REST API と生成済み OpenAPI Contract をラップします。

- **認証とスコープ制限。** 呼び出しには Personal Access Token（PAT）と明示的な Workspace を
  使用します。Agent が Browser Session、Cookie、別の Workspace に触れることはありません。
- **デフォルトで安全。** Run の作成や停止を含むすべての `POST`/`PATCH`/`DELETE` は、先に
  Preview を表示し、明示的な確認を得た後にのみ実行されます。宣言されていない Status や Field が
  ある場合、Skill は Fail-Closed で停止します。
- **Contract に準拠。** Agent は同梱の OpenAPI Contract で Allowlist に登録された
  `operationId` のみを呼び出し、Raw URL を組み立てることはありません。

Archive はリクエスト時にアプリケーションによって Build され、ブラウザへ配信されます。その実体は
リポジトリで管理される Source Bundle であり、SDK、MCP Server、Marketplace、Installer ではありません。

## クイックスタート

前提条件は Docker Engine/Desktop 26 以降と Docker Compose 2.27 以降です。Installer には標準ホストツール、`curl`、`tar` も必要です。

```bash
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

`surgepilot up` は初回設定を確認し、検証済み Linux Runtime 資産をダウンロードし、セルフホストスタックを起動して Web URL を表示します。新しい Release デプロイでは Demo Load Node はデフォルトで無効なため、Run の前に外部 Linux Load Node を準備してください。

- [完全なクイックスタート](https://latentrun.github.io/SurgePilot/docs/ja/quickstart)
- [最初の Run](https://latentrun.github.io/SurgePilot/docs/ja/first-run)
- [設定リファレンス](https://latentrun.github.io/SurgePilot/docs/ja/configuration)

### ソースから起動

開発または完全なローカルソース実行パス：

```bash
make setup
make start-full-stack
```

公式のソース起動パスでは、現在のネイティブアーキテクチャ向け Linux Runtime を準備または再利用し、Compose 内部 Demo Load Node をデフォルトで起動します。Run が選択できるようにする前に、その Demo Node を SurgePilot へ登録して初期化する必要があります。Demo Profile はソース設定で明示的に無効化できます。

Runtime や Run readiness を必要とせず、ログイン、UI、コントロールプレーン、Monitoring の確認だけを行う場合は `make start-preview` を使用してください。各モードの正確な保証は[起動モード](https://latentrun.github.io/SurgePilot/docs/ja/startup-modes)を参照してください。

## このリポジトリによる新しいモデルのベンチマーク

エンジニアリングライフサイクル全体がリポジトリに保存されているため、本リポジトリはより多面的な
Benchmark としても利用できます。表面的な Interface を生成できるかどうかだけではなく、実際の
根拠からマルチサービスシステムを再構築または拡張できるかを評価できます。スコープを
限定した PRD、SDD、ADR、Slice、Contract、Test をモデルへ与え、次の観点で比較できます。

- P0 Product Loop を再構築できるか、および `make verify` の結果。
- 承認済みかつ既にサポートされている Slice Extension を実装し、Contract の差分、Generated Client
  の最新性、Test を確認できるか。
- Public OpenAPI を再生成し、禁止された Route や Schema が含まれていないことを確認できるか。
- Workspace/Security Enforcement と API/Runner Protocol Boundary を維持できるか。
- Active でない P1/P2 Capability や禁止された Infrastructure を回避できるか。

Make Target と実行環境が対応している場合は、Public API Lifecycle Scenario 用の
`make verify-p2-02-public-api-lifecycle` も利用できます。

## ドキュメント

### ユーザー向け

- [ドキュメントホーム](https://latentrun.github.io/SurgePilot/docs/ja/)
- [クイックスタート](https://latentrun.github.io/SurgePilot/docs/ja/quickstart)
- [起動モード](https://latentrun.github.io/SurgePilot/docs/ja/startup-modes)
- [設定](https://latentrun.github.io/SurgePilot/docs/ja/configuration)
- [最初の Run](https://latentrun.github.io/SurgePilot/docs/ja/first-run)
- [FAQ](https://latentrun.github.io/SurgePilot/docs/ja/faq)

### コントリビューターとレビュー担当者向け

- [コントリビューションガイド](CONTRIBUTING.md)と [Agent ルール](AGENTS.md)
- [SDD エントリ](docs/sdd/README.md)と[スコープゲート](docs/sdd/00-product-scope-and-priority.md)
- [アーキテクチャ概要](docs/sdd/01-architecture-overview.md)と[開発フロー](docs/sdd/02-repo-structure-and-dev-workflow.md)
- [API 契約](docs/sdd/04-api-contract-guidelines.md)と [Runner プロトコル](docs/sdd/05-runner-protocol-and-run-state-machine.md)
- [テスト戦略](docs/sdd/09-testing-and-acceptance-strategy.md)
- [ADR インデックス](docs/sdd/adr/README.md)、[P1 Slice インデックス](docs/sdd/slices/P1-README.md)、[P2 Slice インデックス](docs/sdd/slices/P2-README.md)

## コントリビューション

変更を作成する前に [CONTRIBUTING.md](CONTRIBUTING.md) と [AGENTS.md](AGENTS.md) を確認してください。貢献は人間または AI が作成でき、レビューは提出された変更とリポジトリ契約に基づきます。

ホストモード開発、マイグレーション、契約生成、検証は[開発フロー](docs/sdd/02-repo-structure-and-dev-workflow.md)と現在の [`Makefile`](Makefile)に従ってください。README の要約からコマンド動作を推測しないでください。

## ライセンス

SurgePilot は [MIT License](LICENSE) で提供されます。
