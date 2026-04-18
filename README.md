# loto-predict

GCP ベースの **ロト6・ロト7 予想番号生成 & LINE 通知システム** です。
過去当せん番号データを取得し、BigQuery に蓄積し、統計ベースで予想番号を生成して LINE に通知します。

---

## 概要

このシステムは、以下の流れで動作します。

```text
Cloud Scheduler
  ↓
fetch_loto_results
  ↓
Pub/Sub
  ↓
import_loto_results_to_bq
  ↓
Pub/Sub
  ↓
generate_prediction_and_notify
```

### 処理の流れ

1. Cloud Scheduler が抽選日夜に `fetch_loto_results` を起動
2. `fetch_loto_results` が公式ページから最新当せん結果を取得
3. 取得結果を CSV 化して GCS に保存
4. GCS キーを Pub/Sub メッセージとして publish
5. `import_loto_results_to_bq` が Pub/Sub 経由で起動
6. CSV を BigQuery に取り込み
7. 取り込み完了メッセージを Pub/Sub に publish
8. `generate_prediction_and_notify` が Pub/Sub 経由で起動
9. BigQuery の履歴データから予想番号を生成
10. LINE に Push 通知
11. 各処理結果を `execution_logs` に記録

---

## 実装整合ガイド（2026-04）

以下は現行実装に合わせた運用上の正しい前提です。

### 各コンポーネントの責務

- `fetch_loto_results`:
  - 最新当せん結果取得
  - CSV正規化
  - GCS保存
  - importトピック publish
- `import_loto_results_to_bq`:
  - GCS CSV読込
  - CSV行パース
  - draw_no 重複除外
  - BigQuery投入
  - notifyトピック publish
- `generate_prediction_and_notify`:
  - Pub/Subデコード・入力検証
  - repository / LINE client 生成
  - UseCase呼び出し
- `GenerateAndNotifyUseCase`:
  - 履歴取得（最新順）
  - 予想生成
  - メッセージ組み立て
  - LINE送信（localはdry-run）
  - 実行記録保存

### 必須環境変数

最低限、次を設定してください。

- `APP_ENV` (`local` or `gcp`)
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `BQ_DATASET`
- `GCS_BUCKET_RAW`
- `PUBSUB_IMPORT_TOPIC`
- `PUBSUB_NOTIFY_TOPIC`
- `HISTORY_LIMIT_LOTO6`
- `HISTORY_LIMIT_LOTO7`
- `PREDICTION_COUNT`
- `LINE_CHANNEL_ACCESS_TOKEN`（gcpのみ必須）
- `LINE_USER_ID`（gcpのみ必須）

`BQ_DATASET` が標準です。`BIGQUERY_DATASET` は互換用途としてのみ扱い、運用設定は `BQ_DATASET` に統一してください。

`APP_ENV=local` の場合は、`LINE_CHANNEL_ACCESS_TOKEN` と `LINE_USER_ID` は未設定でも実行できます。
このとき通知は `NoopLineClient` により dry-run で処理されます。

### 予想ロジックの考え方

- UseCase が履歴を取得し、`statistics.py` で番号ごとの出現頻度スコアを算出します。
- `prediction.py` ではそのスコアを重みに変換して、重み付きランダム（重複なし）で1口ずつ生成します。
- 同一実行内で同一組合せは再利用しません（集合比較で重複判定）。
- 1口内の表示順は「スコア降順・同点は番号昇順」です。
- 生成要求が組合せ総数を超える場合は `ValueError` を返します。

### ローカル実行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-base.txt
pip install -r requirements-local.txt
```

`.env.local.sample` を `.env.local` として配置し、`APP_ENV=local` を設定してください。

- local の `generate_prediction_and_notify` は `NoopLineClient` を使う dry-run で動作します。
- 実LINE送信は行わず、送信内容をログ出力します。

### Backfill 実行

ローカル:

```powershell
python jobs/backfill_loto_history/main.py --lottery-type loto6 --start-date 2026-01-01 --end-date 2026-04-01 --output-path ./local_storage/backfill/loto6_20260101_20260401.csv
```

Cloud Run Job:

- `infra/backfill_job.tf` は backfill 専用コンテナ image を前提に実行します。
- 必須引数 `--lottery-type --start-date --end-date --output-path` は Terraform 側で `command/args` として設定します。
- 手動実行時は `gcloud run jobs execute ... --args` で上書き可能です。

例:

```powershell
gcloud run jobs execute backfill-loto-history --region=asia-northeast1 --args="jobs/backfill_loto_history/main.py,--lottery-type,loto7,--start-date,2026-01-01,--end-date,2026-04-01,--output-path,gs://<raw-bucket>/backfill/loto7_20260101_20260401.csv"
```

### 動作確認コマンド

```powershell
pytest -q
python -m compileall functions src jobs tests
```

ローカルで通知フロー確認（LINE送信はdry-run）:

```powershell
python -c "from src.usecases.loto_prediction_usecase import generate_and_notify_prediction; print(generate_and_notify_prediction('loto6'))"
```

---

## 特徴

- GCP サーバーレス構成
- Pub/Sub による疎結合な関数連携
- BigQuery による履歴管理
- `execution_id` による一連処理の追跡
- 重複インポート防止
- 重複通知防止
- `common/` による関数共通処理の集約

---

## アーキテクチャ

```text
Cloud Scheduler
  └─> fetch-loto-results (Cloud Functions Gen2)
         ├─ みずほ公式ページから最新結果取得
         ├─ CSV化
         ├─ GCS(raw bucket) に保存
         └─ Pub/Sub(import-loto-results) に publish

Pub/Sub(import-loto-results)
  └─> import-loto-results-to-bq (Cloud Functions Gen2)
         ├─ GCS の CSV を読み込み
         ├─ 重複チェック
         ├─ BigQuery に取り込み
         └─ Pub/Sub(notify-loto-prediction) に publish

Pub/Sub(notify-loto-prediction)
  └─> generate-prediction-and-notify (Cloud Functions Gen2)
         ├─ BigQuery から履歴取得
         ├─ 統計ベース予想生成
         ├─ prediction_runs に保存
         └─ LINE に Push 通知
```

---

## ディレクトリ構成

```text
.
├─ .github/
│  └─ workflows/
│     ├─ deploy-function-source.yml
│     │   └─ Cloud Functions のソースを zip 化して GCS にアップロード
│     │      （common/ を各 function に同梱する処理もここで実施）
│     │
│     └─ terraform-infra.yml
│         └─ Terraform によるインフラ構築（Cloud Functions / BQ / Pub/Sub 等）
│
├─ functions/
│  ├─ common/
│  │  ├─ __init__.py
│  │  ├─ execution_log.py
│  │  │   └─ BigQuery execution_logs への書き込み & Cloud Logging 出力
│  │  │
│  │  ├─ pubsub_message.py
│  │  │   └─ Pub/Sub メッセージの decode / validate / encode 共通処理
│  │  │
│  │  └─ time_utils.py
│  │      └─ JST 時刻生成・ISOフォーマット変換などの共通ユーティリティ
│  │
│  ├─ fetch_loto_results/
│  │  ├─ main.py
│  │  │   └─ Cloud Scheduler から起動される入口
│  │  │      ・公式サイトから当せん結果取得
│  │  │      ・CSV生成
│  │  │      ・GCS保存
│  │  │      ・Pub/Sub publish（import トリガー）
│  │  │
│  │  └─ requirements.txt
│  │      └─ requests / BeautifulSoup 等の依存関係
│  │
│  ├─ import_loto_results_to_bq/
│  │  ├─ main.py
│  │  │   └─ Pub/Sub push で起動
│  │  │      ・GCS の CSV を読み込み
│  │  │      ・重複チェック（draw_no / file_name）
│  │  │      ・BigQuery へ insert
│  │  │      ・Pub/Sub publish（notify トリガー）
│  │  │
│  │  └─ requirements.txt
│  │      └─ google-cloud-bigquery / storage 等
│  │
│  └─ generate_prediction_and_notify/
│     ├─ main.py
│     │   └─ Pub/Sub push で起動
│     │      ・BigQuery から履歴取得
│     │      ・予想番号生成（重み付きランダム）
│     │      ・prediction_runs に保存
│     │      ・LINE Push 通知
│     │
│     └─ requirements.txt
│         └─ BigQuery / LINE API 用ライブラリ
│
├─ infra/
│  ├─ backend.tf
│  │   └─ Terraform の state 管理（GCS backend 設定）
│  │
│  ├─ main.tf
│  │   └─ GCP リソース定義の本体
│  │      ・Cloud Functions Gen2
│  │      ・Pub/Sub
│  │      ・BigQuery
│  │      ・Cloud Scheduler
│  │      ・IAM
│  │
│  ├─ providers.tf
│  │   └─ Google Provider 設定（project / region）
│  │
│  ├─ variables.tf
│  │   └─ 環境依存パラメータ定義
│  │      （project_id / region / dataset / secret_id 等）
│  │
│  └─ versions.tf
│      └─ Terraform / Provider のバージョン固定
│
├─ scripts/
│  └─ package_functions.sh
│      └─ 各 Cloud Functions を zip 化するスクリプト
│         ・common/ を各 function にコピー
│         ・dist/ に成果物を出力
│
├─ dist/
│  └─ （自動生成）
│      ├─ fetch_loto_results.zip
│      ├─ import_loto_results_to_bq.zip
│      └─ generate_prediction_and_notify.zip
│
└─ README.md
    └─ プロジェクト全体の説明ドキュメント
```

---

## Cloud Functions の役割

### 1. fetch_loto_results

役割:

- Cloud Scheduler から HTTP 起動
- ロト6 / ロト7 の最新当せん結果を取得
- CSV に変換
- GCS に保存
- import 用 Pub/Sub にメッセージ送信

入力:

```json
{
  "lottery_type": "LOTO6"
}
```

出力メッセージ例:

```json
{
  "event_type": "FETCH_COMPLETED",
  "execution_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "lottery_type": "LOTO6",
  "gcs_bucket": "your-raw-bucket",
  "gcs_object": "loto6/draw_date=2026-04-05/draw_no=1234/xxxx.csv",
  "draw_no": 1234,
  "draw_date": "2026-04-05",
  "fetched_at": "2026-04-05T19:05:00+09:00"
}
```

---

### 2. import_loto_results_to_bq

役割:

- Pub/Sub push で起動
- GCS の CSV を読み込み
- 重複チェック
- BigQuery の履歴テーブルに取り込み
- notify 用 Pub/Sub にメッセージ送信

重複防止:

- `draw_no`

---

### 3. generate_prediction_and_notify

役割:

- Pub/Sub push で起動
- BigQuery 履歴データを読み込み
- 出現頻度ベースの重み付きランダムで予想生成
- `prediction_runs` に保存
- LINE Push 通知

重複防止:

- `execution_id` 単位で同一実行を追跡

---

## execution_id とは

`execution_id` は、**1回の処理全体を識別するID** です。

この ID を使って、

- fetch
- import
- notify

のすべてを同じ単位で追跡します。

例:

```text
execution_id = 20260405-loto6-001
```

用途:

- 重複実行防止
- ログ追跡
- 障害調査

---

## BigQuery テーブル

### loto6_history

ロト6当せん履歴

主なカラム:

- `draw_no`
- `draw_date`
- `lottery_type`
- `n1 ... n6`（`n7` は `NULLABLE`）
- `b1`（`b2` は `NULLABLE`）
- `source_url`
- `created_at`

### loto7_history

ロト7当せん履歴

主なカラム:

- `draw_no`
- `draw_date`
- `lottery_type`
- `n1 ... n7`
- `b1`
- `b2`
- `source_url`
- `created_at`

### prediction_runs

予想生成結果（1口=1行）

主なカラム:

- `execution_id`
- `lottery_type`
- `draw_no`
- `draw_date`
- `prediction_index`
- `n1 ... n6`（`n7` は `NULLABLE`）
- `message_sent`
- `created_at`

### execution_logs

実行ログ（処理監査）

主なカラム:

- `execution_id`
- `lottery_type`
- `stage`
- `status`
- `message`
- `error_detail`
- `created_at`

`prediction_runs` は予想結果の監査、`execution_logs` は fetch/import/generate の SUCCESS/FAILED を含む実行監査に使います。

---

## 重複防止の考え方

### import 側

以下のどちらかに該当したら取り込みをスキップします。

- 同じ `draw_no`

### notify 側

以下に該当したら通知をスキップします。

- 同じ `execution_id` の再処理が検知された場合

---

## 共通モジュール

`functions/common/` では次を共通化しています。

### execution_log.py

- `execution_logs` への書き込み
- Cloud Logging との統一出力

### pubsub_message.py

- Pub/Sub push リクエストの decode
- 必須項目チェック
- publish 用 bytes 生成

### time_utils.py

- JST 現在時刻取得
- ISO 文字列変換

---

## GitHub Actions

### 1. deploy-function-source.yml

役割:

- `functions/` 配下のソースを zip 化
- `common/` を各 zip に同梱
- GCS の function source bucket にアップロード

アップロード先:

```text
functions/fetch_loto_results/function-source.zip
functions/import_loto_results/function-source.zip
functions/generate_prediction_and_notify/function-source.zip
```

---

### 2. terraform-infra.yml

役割:

- Terraform init / validate / plan / apply
- Cloud Functions / BigQuery / Pub/Sub / Scheduler / IAM を構築

---

## 必要な GitHub Variables

```text
GCP_PROJECT_ID
GCP_REGION
TFSTATE_BUCKET
FUNCTION_SOURCE_BUCKET
BQ_DATASET
HISTORY_LIMIT_LOTO6
HISTORY_LIMIT_LOTO7
LINE_CHANNEL_ACCESS_TOKEN_SECRET_ID
LINE_USER_ID_SECRET_ID
```

---

## 必要な GitHub Secrets

```text
WIF_PROVIDER
WIF_SERVICE_ACCOUNT
FUNCTIONS_RUNTIME_SERVICE_ACCOUNT_EMAIL
SCHEDULER_INVOKER_SERVICE_ACCOUNT_EMAIL
```

---

## 必要な GCP リソース前提

この Terraform は、以下を作成または利用します。

- Cloud Functions Gen2
- Cloud Scheduler
- Pub/Sub Topic / Subscription
- BigQuery Dataset / Tables
- GCS Raw Bucket
- Secret Manager
- IAM Binding

---

## Secret Manager

以下 2 つの secret は事前作成前提です。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_USER_ID
```

Terraform では secret の**ID**を変数で受け取り、Cloud Functions の Secret Environment Variables に設定します。

---

## ブランチ運用

- `develop` への push で function / job のデプロイワークフローを動かし、Terraform は plan / validate を実行します。
- `main` への push では同じワークフローに加えて Terraform apply を実行します。
- そのため、コード修正は `develop` で検証し、`main` を本番反映の基準にします。

---

## ローカル実行

1. `.env.local.sample` を `.env.local` として用意し、`APP_ENV=local` と `LINE_USER_ID` を設定します。
2. `LOCAL_STORAGE_PATH` 配下に CSV を保存するので、ローカルでは GCS なしでも実行できます。
3. 予想確認は `pytest`、バックフィルは `python jobs/backfill_loto_history/main.py --lottery-type loto6 --start-date 2026-01-01 --end-date 2026-04-01 --output-path ./local_storage/backfill.csv` のように実行できます。

---

## スケジュール

### ロト6

- 月曜・木曜
- 19:05 JST

```text
5 19 * * 1,4
```

### ロト7

- 金曜
- 19:05 JST

```text
5 19 * * 5
```

---

## ローカルでの zip 作成

```bash
bash ./scripts/package_functions.sh
```

生成物:

```text
dist/fetch_loto_results.zip
dist/import_loto_results_to_bq.zip
dist/generate_prediction_and_notify.zip
```

確認例:

```bash
unzip -l dist/fetch_loto_results.zip
```

`common/` が含まれていれば OK です。

---

## デプロイ手順

### 1. function source zip をアップロード

GitHub Actions:

- `Deploy Function Source`

### 2. Terraform 適用

GitHub Actions:

- `Terraform Infra`

---

## ログ確認

### BigQuery

`execution_logs` を使って、1回の実行全体を追えます。

例:

```sql
SELECT
  execution_id,
  stage,
  status,
  message,
  created_at
FROM `YOUR_PROJECT.YOUR_DATASET.execution_logs`
WHERE execution_id = '対象execution_id'
ORDER BY created_at ASC
```

### Cloud Logging

`execution_id` で検索すると追いやすいです。

例:

```text
jsonPayload.execution_id="対象execution_id"
```

---

## 設計方針

このシステムは、以下を重視しています。

- 取得・取込・通知の責務分離
- Pub/Sub による非同期連携
- GCS を実データ置き場、Pub/Sub をイベント通知として利用
- `execution_id` による一連処理のトレース
- BigQuery による監査・検証しやすい構成
- Secret のコード直書き禁止

---

## 設計・実装のベストプラクティス

このリポジトリは、以下の設計・実装方針を徹底しています。

- **型ヒント・docstringの徹底**: すべての関数・クラスに型ヒントとdocstringを付与し、保守性・可読性を最大化
- **責務分離の厳守**: ドメイン・ユースケース・インフラ層を明確に分離し、各層の責務を厳格に管理
- **アンチパターン禁止**:
  - ドメイン層から外部サービス呼び出し禁止
  - usecase層から直接インフラサービス呼び出し禁止（必ずI/F経由）
  - os.environ等の直接参照禁止（設定はconfig/やSecret Manager経由）
- **テスト容易性の担保**: ドメイン層は純粋関数・副作用なし、usecase層は外部I/Fを注入可能な設計
- **CI/CD・運用の工夫**: GitHub Actionsでの自動デプロイ・TerraformによるIaC・Secret管理の徹底

### 参考: 具体的な実装例

- ドメイン層: `src/domain/`（外部依存なし、純粋関数・データクラスのみ）
- ユースケース層: `src/usecases/`（インフラI/Fを注入し、ロジックをオーケストレーション）
- インフラ層: `src/infrastructure/`（GCP/LINE等の外部サービスラッパー）
- テスト: `tests/`（pytestベース、外部I/Fはmonkeypatchでモック）

---

## 注意点

- 取得元ページの HTML 構造が変わると `fetch_loto_results` の解析ロジック修正が必要です
- 予想番号は統計参考値であり、当せんを保証するものではありません
- 現在の予想ロジックは軽量な重み付きランダム方式です
- 機械学習モデルは導入していません
