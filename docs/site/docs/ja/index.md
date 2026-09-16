---
layout: home

hero:
  name: SurgePilot ユーザードキュメント
  text: AI 駆動の分散 API 負荷テスト
  tagline: 最初の公開ベースラインは AI Agent が作成。再利用可能なリクエストフローを設計し、複数ノードで分散負荷テストを実行して、エンジン設定の手間を抑えながらリアルタイムメトリクスを確認できます。
  image:
    src: /surgepilot-hero.webp
    alt: Illustrative SurgePilot AI load-testing artwork; not a performance benchmark
  actions:
    - theme: brand
      text: クイックスタート
      link: /docs/ja/quickstart
    - theme: alt
      text: 起動モード
      link: /docs/ja/startup-modes
    - theme: alt
      text: 用語と FAQ
      link: /docs/ja/faq

features:
  - title: 🤖 最初の AI 作成ベースライン
    details: 最初のベースラインは人間の指示のもとで AI Agent が作成し、責任範囲と証拠マップを確認できるように記録しています。
  - title: ⚡ 1 コマンドで Bootstrap
    details: "`surgepilot up` を実行すると、Web UI、FastAPI Control Plane、PostgreSQL、MinIO、Nginx、ホスト上の InfluxDB/Grafana Monitoring を含むフルスタックを対話形式で設定し、数秒で起動できます。"
  - title: 🧾 監査可能なエンジニアリング証拠
    details: ガバナンス文書、Contract、テスト、リリース資産により、プロダクト意図から検証までを確認できます。
  - title: 🌐 分散 Linux Runner
    details: Control Plane と実行エンジンを分離。SSH/SFTP 経由でリモート Linux Load Node を自動化し、複数ノードのメトリクス集約とリアルタイム InfluxDB ストリーミングに対応します。
  - title: 🔒 データと Secret の分離
    details: 複数チームの Workspace 分離、保存時に暗号化される Load Node の認証情報、マスクされた Env Group Secret Variable、Contract に基づくロール権限チェックを備えています。
  - title: 📊 信頼できる判定とレポート
    details: 再利用可能なリクエストフローと負荷モデルにより、決定的な PASS/FAIL 判定、詳細なレスポンスメトリクス、失敗内訳、ダウンロード可能な Run Artifact を提供します。
---

## SurgePilot とは？

SurgePilot は、API 負荷テストを設計、実行、レビューするためのセルフホスト型
プラットフォームです。再利用可能なリクエストフローを環境値や負荷設定から分離し、1 台以上の
Linux Load Node で実行します。

SurgePilot は、自ら運用するインフラストラクチャ上で、制御された負荷テストワークフローを
必要とする開発者、パフォーマンスエンジニア、社内 Platform Team を対象としています。

## コアワークフロー

SurgePilot は、何をテストするかと、どのように・どこで実行するかを分離します。

- **Scenario** — 再利用可能な API とビジネスリクエストフローを定義します。
- **Env Group** — フローを変更せずに環境固有の値を提供します。
- **Test Plan** — Scenario に負荷設定、実行リソース、合否基準を組み合わせます。
- **Load Node** — テストを実行する Linux ホストを提供します。
- **Run Report** — 判定、メトリクス、診断情報、Artifact を確認します。

## 🔄 最短の利用手順

1. [クイックスタート](./quickstart.md)に従い、`surgepilot up` でフルスタックを起動します。
2. [初回実行](./first-run.md)を参照して、環境、Scenario、Test Plan を作成します。
3. [Load Node](./first-run.md#prepare-a-load-node) を関連付け、最初の制御された Run を実行します。
4. プロダクト用語や起動境界が不明な場合は、[用語と FAQ](./faq.md)を確認します。

::: warning テスト権限のあるシステムだけを対象にしてください
小規模な負荷テストでも実際のトラフィックが発生します。自分が所有している、または明示的な
許可を得ている非本番環境に対して、低い同時実行数と短い実行時間から始めてください。
:::

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
