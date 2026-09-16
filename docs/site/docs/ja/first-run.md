# はじめての Run

このガイドでは、環境変数 → Scenario → Test Plan → Run → レポートという、最小限の実用的な流れを作成します。

始める前に、[タグ付きリリースまたはソースのフルスタック](./quickstart.md)を起動してください。Source Preview では Runtime や Load Node が準備されないため、この手順には使用できません。

::: warning 安全なテスト対象を使用してください
自分が所有している、またはテストする明示的な許可を得ている非本番環境のエンドポイントを選んでください。最初の負荷は、同時ユーザー 1、実行時間 60 秒に抑えます。
:::

## ステップ 1：最初の Admin を登録する

起動時に表示された Web URL を開き、**Sign up** を選択します。最初に登録したアカウントが Admin となり、**Default Workspace** が作成されます。2 人目以降の登録可否は、デプロイ時に設定したサインアップポリシーに従います。

## ステップ 2：Env Group を作成する

Env Group を使うと、環境固有の値を再利用可能な Scenario から分離して管理できます。

1. **Assets → Env Groups** を開きます。
2. **New Env Group** を選択します。
3. 名前を `local` にします。
4. キーが `base_url` の通常変数を追加し、テスト対象の完全なオリジン（例：`https://test-api.example.com`）を入力します。
5. **Save Env Group** を選択します。

`base_url` の **Secret** はオフのままにしてください。Secret の値は保存後に読み出せず、マスク表示されます。通常の接続先アドレスではなく、認証情報などに使用するための機能です。

## ステップ 3：Load Node の準備 {#prepare-a-load-node}

Run を実行するには、初期化済みで **Idle** 状態の Load Node が 1 台以上必要です。SurgePilot の起動方法に合う手順を選んでください。

### ソースのフルスタック：Demo node を登録する

`make start-full-stack` は Compose 内に SSH node を起動し、接続情報を表示します。リポジトリのルートでホストキーのフィンガープリントを確認し、生成されたパスワードをローカルで読み取ります。

```sh
ssh-keygen -lf .surgepilot/demo-load-node/ssh_host_ed25519_key.pub -E sha256
cat .surgepilot/secrets/demo-load-node-password.secret
```

パスワードは機密情報として扱い、Issue、ログ、ソースファイルには貼り付けないでください。

SurgePilot で次の操作を行います。

1. **Resources → Load Nodes** を開き、**Register Load Node** を選択します。
2. **Scope** は **Private** のままにします。
3. Host に `demo-load-node`、Port に `22`、SSH user に `surgepilot` を入力します。
4. **Scan key** を選択します。表示された SHA-256 フィンガープリントを `ssh-keygen` の出力と照合し、確認できたキーを採用します。
5. 認証方式に **Password** を選び、生成されたパスワードを入力します。
6. **Runner home** は空欄のままにして API のデフォルト値を使用し、**Register Load Node** を選択します。
7. **Load Nodes** に戻り、`demo-load-node` の **Initialize** を選択して、状態が **Idle** になるまで待ちます。

### タグ付きリリース：外部 node を登録する

タグ付きリリースでは Demo node は無効です。次の条件を満たす Linux マシンを用意してください。

- Ubuntu 24.04 以降、または Debian 12 以降。
- `x86_64`（`amd64`）または `aarch64`（`arm64`）。
- SurgePilot API から SSH 接続できること。
- `tar`、POSIX shell、Java 11 以降、Python 3.12 以降が利用できること。

**Resources → Load Nodes → Register Load Node** を開き、SSH 接続情報を入力します。ホストキーのフィンガープリントを取得し、別の信頼できる経路で照合したうえで、対応する認証情報を入力してください。登録後に **Initialize** を選択し、状態が **Idle** になるまで待ちます。この node から、`surgepilot up` の実行時に確認した API と InfluxDB の node 向け URL にアクセスできる必要があります。

## ステップ 4：Scenario を作成する

Scenario は、順序を持つ再利用可能なリクエストフローです。

1. **Scenarios** を開き、**Create Scenario** を選択します。
2. 名前を `health-check`、**Base URL expression** を `${base_url}` に設定します。
3. 作成した Scenario を開き、**Add Step** を選択します。
4. Method は **GET** のままにし、`/health` など安全なパスを入力します。テスト対象の正常なステータスが `200` なら、デフォルトの期待ステータス assertion をそのまま使用します。
5. **Save** を選択します。

`local` Env Group と Idle 状態の node を選択すれば、**Debug Run** で集中的な動作確認ができます。Debug Run は node を 1 台だけ使用し、Monitoring データを送信しません。そのまま低負荷の Test Plan 作成へ進んでも構いません。

## ステップ 5：Test Plan を作成する

Test Plan は、保存済みの Scenario に Env Group、負荷設定、実行リソース、任意の SLA ルールを組み合わせたものです。

1. **Test Plans** を開き、**Create Test Plan** を選択します。
2. 名前を `health-check-low-load` にして作成します。
3. **Global Context** で `local` Env Group を選択します。
4. **Resource Configuration** で **Manual selected nodes** を選び、**Pool Type** を **Private** に設定します。Idle 状態の node を選択して **Done** を押します。
5. **Scenario Orchestration** で **Add Scenario** を選び、`health-check` を追加します。
6. 最初の Run では、**Concurrency / Node** を `1`、**Ramp-up** を `0`、**Hold-for** を `60` のままにします。
7. 必要に応じて、テスト対象に合ったしきい値の SLA ルールを追加します。
8. **Save** を選択します。
9. **Generated YAML Preview** で **Standard** を選び、**Preview YAML** を押します。この Preview は読み取り専用で、最後に保存した Test Plan の revision が反映されます。

## ステップ 6：実行して結果を確認する

**Run Now** を選択します。Run の進行中は Run Report が表示されます。terminal state になるまで待ってから、次の項目を確認してください。

- **Verdict Summary**：Run の状態、validity、SLA の結果。
- **KPI Summary** と **Final Stats Preview**：レスポンスとエラーのメトリクス。
- **Failure Diagnostics**：Run が想定どおりに完了しなかった場合の診断情報。
- **Snapshot Summary**：この Run で使用された immutable な設定。
- **Artifacts**：ダウンロード可能なログと結果ファイル。
- **Nodes**：node ごとの実行状態。

後から確認する場合は **Runs** を開き、**View Report** を選択します。レポートは、保存された Run snapshot の記録です。その後に Env Group、Scenario、Test Plan を編集しても、過去の記録が書き換わることはありません。

*この日本語訳は AI の支援により作成されています。英語版と内容が異なる場合は、英語版を正とします。*
