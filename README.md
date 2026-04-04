# 🎯 Loto Predict Line

ロト6・ロト7の過去当選データをもとに、
**統計集計 → 重み付き予想番号生成 → LINE通知** までを自動実行する
**個人利用向けのGCPサーバーレスシステム**です。

---

## 🚀 特徴

- 🎲 ロト6 / ロト7の予想番号を自動生成
- 📊 BigQueryを用いた過去データ分析
- ⚖️ 重み付きランダムによる現実的な予測
- 📩 LINE Messaging APIで自動通知
- ☁️ Cloud Functions + Schedulerによる完全自動化
- 🐳 Docker Composeでローカル実行可能
- 🏗 Terraformでインフラ管理

---

## 🧠 システム概要

```text
Cloud Scheduler
   ↓
Cloud Functions (entry_point)
   ↓
UseCase層
   ├─ BigQuery から履歴取得
   ├─ 統計集計
   ├─ スコア算出
   ├─ 予想番号生成
   ├─ prediction_runs 保存
   └─ LINE通知
```

---

## 🗂 ディレクトリ構成

```text
loto-predict/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
├── main.py
├── requirements.txt
├── config/
├── domain/
├── usecases/
├── infrastructure/
├── utils/
├── tests/
├── docs/
├── bootstrap/         # Terraform（初期構築）
├── infra/             # Terraform（本体）
├── .devcontainer/     # Terraform作業専用
└── .github/workflows/
```

---

## 🧩 技術スタック

| 分類     | 技術                 |
| -------- | -------------------- |
| 言語     | Python 3.12          |
| 実行基盤 | Cloud Functions Gen2 |
| データ   | BigQuery             |
| 通知     | LINE Messaging API   |
| IaC      | Terraform            |
| ローカル | Docker Compose       |
| 認証     | gcloud ADC           |

---

## ⚙️ セットアップ

### 1. リポジトリ取得

```bash
git clone https://github.com/yantzn/loto-predict.git
cd loto-predict
```

---

### 2. 環境変数設定

```bash
cp .env.example .env
```

`.env` を編集してください：

```env
LINE_CHANNEL_ACCESS_TOKEN=xxx
LINE_USER_ID=xxx
```

---

### 3. GCP認証（必須）

```bash
gcloud auth application-default login
gcloud config set project loto-predict-491915
```

---

### 4. ローカル起動

```bash
docker compose up --build
```

起動後：

```text
http://localhost:8080
```

---

## 🧪 動作確認

### ロト6

```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "lottery_type": "LOTO6",
    "draw_no": 2000
  }'
```

---

### ロト7

```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "lottery_type": "LOTO7",
    "draw_no": 650
  }'
```

---

## 🌍 環境変数一覧

| 変数                      | 説明              |
| ------------------------- | ----------------- |
| GCP_PROJECT_ID            | GCPプロジェクトID |
| BIGQUERY_DATASET          | データセット      |
| LINE_CHANNEL_ACCESS_TOKEN | LINEトークン      |
| LINE_USER_ID              | 通知先            |
| STATS_TARGET_DRAWS        | 集計対象回数      |
| PREDICTION_COUNT          | 生成口数          |

詳細は `.env.example` を参照。

---

## ⏰ スケジューラー

| 種類  | cron           |
| ----- | -------------- |
| ロト6 | `5 19 * * 1,4` |
| ロト7 | `5 19 * * 5`   |

---

## 🏗 Terraform（インフラ）

Terraform操作は `.devcontainer` を使用します。

### 起動方法

VS Codeで：

```
Reopen in Container
```

---

### 実行

```bash
cd bootstrap
terraform init
terraform apply

```

---

## 🔥 エラーハンドリング

主なエラー分類：

- CONFIG_ERROR
- VALIDATION_ERROR
- BIGQUERY_ERROR
- PREDICTION_ERROR
- LINE_ERROR

---

## ⚠️ 注意事項

- 本プロジェクトは個人利用前提です
- 当選を保証するものではありません
- 秘密情報は必ず環境変数 or Secret Managerで管理してください

---

## 🧭 開発方針

| 項目         | 方針            |
| ------------ | --------------- |
| ローカル実行 | Docker Compose  |
| インフラ作業 | `.devcontainer` |
| 仮想環境     | 使用しない      |
| 再現性       | コンテナで担保  |

---

## 💡 今後の拡張

- UI（Web / Flutter）
- 予測ロジックの高度化（機械学習）
- 当選結果との比較分析
- 通知フォーマット改善

---

## 👤 Author

zono

---
