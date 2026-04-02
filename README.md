# 🎯 Loto Predict Line

ロト6・ロト7の過去当選データをもとに、
**統計集計 → 重み付き予想番号生成 → LINE通知** までを自動実行する
**個人利用向けの GCP サーバーレスシステム**です。

- **言語**: Python
- **実行基盤**: GCP Cloud Functions / Cloud Scheduler / BigQuery
- **通知**: LINE Messaging API
- **用途**: 個人向け参考予想の自動配信

> 本システムは過去データに基づく参考情報の生成を目的としたものです。
> 当選を保証するものではありません。

---

# 1. システム概要

本システムは、ロト6・ロト7の過去当選番号を BigQuery に蓄積し、
直近 N 回の出現傾向をもとに数字ごとのスコアを算出します。

そのスコアを使って、各数字の当選しやすさを参考値として扱いながら、
**重み付きランダム方式**で予想番号を 5口生成し、LINE に Push 通知します。

---

# 2. 主な機能

- ロト6 / ロト7 の過去当選データ保存
- BigQuery からの履歴取得
- 直近 N 回の統計集計
- 数字ごとのスコア算出
- 重み付きランダムによる予想番号 5口生成
- LINE Messaging API での本人通知
- Cloud Functions による HTTP / Pub/Sub 実行
- Cloud Scheduler による定期起動
- エラー時のログ出力と処理中断

---

# 3. アーキテクチャ

```text
Cloud Scheduler
   ↓
Cloud Functions (main.py / entry_point)
   ↓
LotoPredictionUseCase
   ├─ BigQuery から履歴取得
   ├─ 統計集計
   ├─ 予想番号 5口生成
   ├─ prediction_runs 保存
   └─ LINE Push 通知
```

---

# 4. ディレクトリ構成

```text
loto-predict-line/
├─ README.md                # プロジェクト説明・セットアップ手順
├─ requirements.txt        # 必要なPythonパッケージ一覧
├─ .gitignore              # Git管理対象外ファイル定義
├─ main.py                 # Cloud Functionsエントリポイント
│
├─ config/                 # 設定管理用モジュール
│  ├─ __init__.py
│  └─ settings.py          # 環境変数や定数の定義
│
├─ utils/                  # 汎用ユーティリティ
│  ├─ __init__.py
│  ├─ exceptions.py        # 独自例外定義
│  ├─ logger.py            # ログ出力ユーティリティ
│  └─ validators.py        # 入力バリデーション
│
├─ domain/                 # ドメインロジック（ビジネスルール）
│  ├─ __init__.py
│  ├─ models.py            # エンティティ・データ構造
│  ├─ statistics.py        # 統計計算ロジック
│  └─ prediction.py        # 予想生成ロジック
│
├─ infrastructure/         # 外部サービス連携・データアクセス
│  ├─ __init__.py
│  ├─ bigquery_client.py   # BigQuery操作ラッパー
│  ├─ loto_repository.py   # ロトデータ永続化リポジトリ
│  ├─ data_fetcher.py      # 外部データ取得
│  └─ line_client.py       # LINE API連携
│
├─ usecases/               # ユースケース層（アプリケーションサービス）
│  ├─ __init__.py
│  ├─ data_sync_usecase.py     # データ同期処理
│  ├─ notification_usecase.py  # 通知処理
│  └─ loto_prediction_usecase.py # 予想生成・通知処理
│
├─ docs/                   # ドキュメント
│  ├─ schema.md            # データスキーマ定義
│  └─ deployment.md        # デプロイ手順等
│
└─ tests/                  # テストコード
  ├─ __init__.py
  ├─ test_statistics.py   # 統計ロジックのテスト
  └─ test_prediction.py   # 予想生成ロジックのテスト
```

---

# 5. 依存技術

- Python 3.12
- functions-framework
- google-cloud-bigquery
- line-bot-sdk
- cloudevents

---

# 6. セットアップ

## 6.1 プロジェクト作成

```bash
mkdir -p loto-predict-line
cd loto-predict-line
```

## 6.2 仮想環境作成

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 6.3 依存パッケージインストール

```bash
pip install -r requirements.txt
```

---

# 7. 環境変数

ローカル実行や Cloud Functions で必要な環境変数です。

```bash
APP_ENV=dev
APP_TIMEZONE=Asia/Tokyo

GCP_PROJECT_ID=your-project-id
GCP_REGION=asia-northeast1
BIGQUERY_DATASET=loto_predict

LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token
LINE_USER_ID=your-line-user-id

LOG_LEVEL=INFO
LOG_JSON=true
SERVICE_NAME=loto-predict-line

STATS_TARGET_DRAWS=100
PREDICTION_COUNT=5

LOTO6_NUMBER_MIN=1
LOTO6_NUMBER_MAX=43
LOTO6_PICK_COUNT=6

LOTO7_NUMBER_MIN=1
LOTO7_NUMBER_MAX=37
LOTO7_PICK_COUNT=7
```

---

# 8. BigQuery テーブル

最低限必要なテーブルは以下です。

- `loto6_draw_results`
- `loto7_draw_results`
- `prediction_runs`

## 8.1 loto6_draw_results

- `lottery_type` STRING
- `draw_no` INT64
- `draw_date` DATE
- `main_numbers` ARRAY<INT64>
- `bonus_numbers` ARRAY<INT64>
- `source_type` STRING
- `source_reference` STRING
- `fetched_at` TIMESTAMP
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

## 8.2 loto7_draw_results

- `lottery_type` STRING
- `draw_no` INT64
- `draw_date` DATE
- `main_numbers` ARRAY<INT64>
- `bonus_numbers` ARRAY<INT64>
- `source_type` STRING
- `source_reference` STRING
- `fetched_at` TIMESTAMP
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

## 8.3 prediction_runs

- `lottery_type` STRING
- `draw_no` INT64
- `stats_target_draws` INT64
- `score_snapshot` RECORD(REPEATED)
- `generated_predictions` ARRAY<ARRAY<INT64>> または JSON 相当構成
- `created_at` TIMESTAMP

詳細は `docs/schema.md` に整理してください。

---

# 9. ローカル動作確認

## 9.1 Functions Framework で起動

```bash
functions-framework --target=entry_point --debug
```

## 9.2 HTTP で実行

### ロト6

```bash
curl -X POST "http://localhost:8080" \
  -H "Content-Type: application/json" \
  -d '{
    "lottery_type": "LOTO6",
    "draw_no": 2000,
    "stats_target_draws": 100,
    "prediction_count": 5
  }'
```

### ロト7

```bash
curl -X POST "http://localhost:8080" \
  -H "Content-Type: application/json" \
  -d '{
    "lottery_type": "LOTO7",
    "draw_no": 650,
    "stats_target_draws": 100,
    "prediction_count": 5
  }'
```

---

# 10. 実行フロー

## 10.1 予想生成フロー

1. BigQuery から対象くじの直近 N 回履歴を取得
2. 各数字の出現回数を集計
3. 直近出現を加味したスコアを算出
4. 重み付きランダムで 5口生成
5. `prediction_runs` に保存
6. LINE に Push 通知

## 10.2 データ取り込みフロー

1. CSV / API / スクレイピングなどから当選データ取得
2. 妥当性チェック
3. BigQuery に保存

---

# 11. 統計ロジック

統計処理では、数字ごとに以下を算出します。

- `frequency_count`: 直近 N 回での出現回数
- `weighted_frequency`: 直近ほど重みを高くした加重出現頻度
- `last_seen_index`: 最後に出現した位置
- `recency_bonus`: 直近出現補正
- `final_score`: 最終スコア

この `final_score` を、予想番号生成時の重みとして利用します。

---

# 12. 予想番号生成ロジック

予想生成は単純ランダムではなく、
**統計スコアを反映した重み付きランダム抽選**を使います。

### ルール

- ロト6: 1〜43 から 6個
- ロト7: 1〜37 から 7個
- 各 5口生成
- 同一実行内で同一組合せは不可
- 条件を満たせない場合は例外

### 特徴

- 高スコア数字ほど出現しやすい
- ただし低スコア数字も完全には除外しない
- 重複なしの非復元抽出

---

# 13. LINE通知

LINE Messaging API を使って本人アカウントへ Push 通知します。

通知例:

```text
🎯 LOTO6 予想番号
対象回号: 第2000回

1口目: 02 05 09 14 28 41
2口目: 01 07 12 19 25 33
3口目: 03 08 16 21 34 40
4口目: 04 06 11 18 29 35
5口目: 10 13 17 23 31 42

※過去データに基づく参考予想です。
```

---

# 14. Cloud Functions デプロイ

HTTP トリガーでデプロイする例:

```bash
gcloud functions deploy loto-orchestrator \
  --gen2 \
  --region=asia-northeast1 \
  --runtime=python312 \
  --source=. \
  --entry-point=entry_point \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-env-vars="APP_ENV=prod,APP_TIMEZONE=Asia/Tokyo,GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_REGION=asia-northeast1,BIGQUERY_DATASET=loto_predict,LOG_LEVEL=INFO,LOG_JSON=true,SERVICE_NAME=loto-predict-line,STATS_TARGET_DRAWS=100,PREDICTION_COUNT=5,LOTO6_NUMBER_MIN=1,LOTO6_NUMBER_MAX=43,LOTO6_PICK_COUNT=6,LOTO7_NUMBER_MIN=1,LOTO7_NUMBER_MAX=37,LOTO7_PICK_COUNT=7" \
  --set-secrets="LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest,LINE_USER_ID=LINE_USER_ID:latest"
```

---

# 15. Cloud Scheduler 設定

## ロト6

- 月曜・木曜 19:05 JST
- cron: `5 19 * * 1,4`

## ロト7

- 金曜 19:05 JST
- cron: `5 19 * * 5`

Cloud Scheduler から HTTP で関数を起動し、JSON ボディで対象くじを渡します。

### ロト6

```bash
gcloud scheduler jobs create http loto6-predict-job \
  --location=asia-northeast1 \
  --schedule="5 19 * * 1,4" \
  --time-zone="Asia/Tokyo" \
  --uri="YOUR_FUNCTION_URL" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"lottery_type":"LOTO6","prediction_count":5,"stats_target_draws":100}'
```

### ロト7

```bash
gcloud scheduler jobs create http loto7-predict-job \
  --location=asia-northeast1 \
  --schedule="5 19 * * 5" \
  --time-zone="Asia/Tokyo" \
  --uri="YOUR_FUNCTION_URL" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"lottery_type":"LOTO7","prediction_count":5,"stats_target_draws":100}'
```

---

# 16. エラーハンドリング方針

途中で失敗した場合は処理を中断し、構造化ログに記録します。

主なエラー分類:

- `CONFIG_ERROR`
- `VALIDATION_ERROR`
- `DATA_FETCH_ERROR`
- `BIGQUERY_READ_ERROR`
- `BIGQUERY_WRITE_ERROR`
- `STATISTICS_CALCULATION_ERROR`
- `PREDICTION_GENERATION_ERROR`
- `NOTIFICATION_ERROR`

---

# 17. ログ設計

JSON ログを標準出力へ出します。
主な項目:

- `timestamp`
- `severity`
- `message`
- `service`
- `env`
- `execution_id`
- `lottery_type`
- `event`
- `stage`

Cloud Logging 上で `execution_id` ごとに追跡可能です。

---

# 18. 今後の拡張案

- 他のくじ種別追加
- データ取得元の追加
- Web UI / 手動実行画面
- 通知先の複数化
- Flex Message 対応
- 当選結果との自動照合
- 予想ロジック高度化
- `prediction_runs` の可視化

---

# 19. テスト

今後は以下のテストを追加すると安定します。

- 統計ロジック単体テスト
- 予想生成ロジック単体テスト
- 通知メッセージ整形テスト
- BigQuery リポジトリの統合テスト
- Cloud Functions エントリポイントの HTTP テスト

---

# 20. 注意事項

- 本プロジェクトは個人利用前提です
- 高可用構成は前提にしていません
- 通知や予想結果の正確性は外部データ品質に依存します
- LINE トークン等の秘密情報はコードに含めず Secret Manager を利用してください

---

# 21. ライセンス / 利用方針

個人利用を前提としたサンプル / 自作システムです。
商用利用や第三者配信へ拡張する場合は、権限設計・監査ログ・通知制御・障害対応設計を追加してください。

```

```
