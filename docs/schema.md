以下が **`docs/schema.md` の完全版** です。
そのままファイルとして保存できる形にしています。

````md
# BigQuery Schema Design

本ドキュメントでは、ロト6・ロト7統計予想＆LINE通知システムで利用する
BigQuery のデータセット、テーブル、スキーマ、運用上の考慮点を定義します。

---

# 1. 目的

本システムでは、以下の用途のために BigQuery を利用します。

- ロト6・ロト7の過去当選履歴の保存
- 統計処理用の直近 N 回データの取得
- 予想生成結果の保存
- 後続の分析・検証・改善に使う実行履歴の蓄積

BigQuery は、**履歴保存・参照・簡易分析** を主目的とし、
予想ロジック本体は Python アプリケーション側で実行します。

---

# 2. データセット

推奨データセット名:

```text
loto_predict
```
````

推奨リージョン:

```text
asia-northeast1
```

---

# 3. テーブル一覧

| テーブル名           | 用途                                 |
| -------------------- | ------------------------------------ |
| `loto6_draw_results` | ロト6の当選履歴                      |
| `loto7_draw_results` | ロト7の当選履歴                      |
| `prediction_runs`    | 予想実行履歴                         |
| `execution_logs`     | 任意。実行結果サマリや障害追跡用ログ |

---

# 4. 設計方針

## 4.1 ロト6・ロト7は別テーブルに分ける

ロト6とロト7は数字件数・範囲が異なるため、
1テーブルにまとめず、別テーブルに分けます。

これにより以下の利点があります。

- スキーマが明確
- Python 側のバリデーションと整合しやすい
- クエリ条件が単純になる
- テーブル単位での確認がしやすい

## 4.2 本数字・ボーナス数字は ARRAY で保持する

当選番号は順序付き配列として保持します。

- `main_numbers`: `ARRAY<INT64>`
- `bonus_numbers`: `ARRAY<INT64>`

これにより、後続で `UNNEST()` を使った集計がしやすくなります。

## 4.3 厳密制約はアプリケーション側でも保証する

BigQuery は RDB のような厳密制約には向いていないため、
以下の制約は **Python 側でも必ず検証** します。

- 件数
- 範囲
- 重複
- 本数字とボーナス数字の重複禁止

## 4.4 将来拡張を見据えて監査項目を持つ

取得元・取得時刻・作成時刻・更新時刻を持たせることで、
障害調査やデータ品質確認をしやすくします。

---

# 5. テーブル定義

---

# 5.1 `loto6_draw_results`

## 用途

ロト6の過去当選結果を保存します。

## カラム定義

| カラム名           | 型           | 必須 | 説明                           |
| ------------------ | ------------ | ---: | ------------------------------ |
| `lottery_type`     | STRING       |    ○ | `LOTO6` 固定                   |
| `draw_no`          | INT64        |    ○ | 回号                           |
| `draw_date`        | DATE         |    ○ | 抽選日                         |
| `main_numbers`     | ARRAY<INT64> |    ○ | 本数字6個                      |
| `bonus_numbers`    | ARRAY<INT64> |    ○ | ボーナス数字1個                |
| `source_type`      | STRING       |    ○ | `CSV` / `API` / `SCRAPER` など |
| `source_reference` | STRING       |      | 取得元 URL、ファイル名など     |
| `fetched_at`       | TIMESTAMP    |    ○ | 外部データ取得時刻             |
| `created_at`       | TIMESTAMP    |    ○ | BigQuery 登録時刻              |
| `updated_at`       | TIMESTAMP    |    ○ | 更新時刻                       |

## 論理制約

- `lottery_type = 'LOTO6'`
- `main_numbers` の件数は 6
- `bonus_numbers` の件数は 1
- 数字範囲は 1〜43
- `main_numbers` 内で重複禁止
- `bonus_numbers` 内で重複禁止
- `main_numbers` と `bonus_numbers` の重複禁止
- `draw_no` は実質一意

## 推奨 DDL

```sql
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.loto_predict.loto6_draw_results` (
  lottery_type STRING NOT NULL,
  draw_no INT64 NOT NULL,
  draw_date DATE NOT NULL,
  main_numbers ARRAY<INT64> NOT NULL,
  bonus_numbers ARRAY<INT64> NOT NULL,
  source_type STRING NOT NULL,
  source_reference STRING,
  fetched_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
PARTITION BY draw_date
CLUSTER BY draw_no;
```

---

# 5.2 `loto7_draw_results`

## 用途

ロト7の過去当選結果を保存します。

## カラム定義

| カラム名           | 型           | 必須 | 説明                           |
| ------------------ | ------------ | ---: | ------------------------------ |
| `lottery_type`     | STRING       |    ○ | `LOTO7` 固定                   |
| `draw_no`          | INT64        |    ○ | 回号                           |
| `draw_date`        | DATE         |    ○ | 抽選日                         |
| `main_numbers`     | ARRAY<INT64> |    ○ | 本数字7個                      |
| `bonus_numbers`    | ARRAY<INT64> |    ○ | ボーナス数字2個                |
| `source_type`      | STRING       |    ○ | `CSV` / `API` / `SCRAPER` など |
| `source_reference` | STRING       |      | 取得元 URL、ファイル名など     |
| `fetched_at`       | TIMESTAMP    |    ○ | 外部データ取得時刻             |
| `created_at`       | TIMESTAMP    |    ○ | BigQuery 登録時刻              |
| `updated_at`       | TIMESTAMP    |    ○ | 更新時刻                       |

## 論理制約

- `lottery_type = 'LOTO7'`
- `main_numbers` の件数は 7
- `bonus_numbers` の件数は 2
- 数字範囲は 1〜37
- `main_numbers` 内で重複禁止
- `bonus_numbers` 内で重複禁止
- `main_numbers` と `bonus_numbers` の重複禁止
- `draw_no` は実質一意

## 推奨 DDL

```sql
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.loto_predict.loto7_draw_results` (
  lottery_type STRING NOT NULL,
  draw_no INT64 NOT NULL,
  draw_date DATE NOT NULL,
  main_numbers ARRAY<INT64> NOT NULL,
  bonus_numbers ARRAY<INT64> NOT NULL,
  source_type STRING NOT NULL,
  source_reference STRING,
  fetched_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
PARTITION BY draw_date
CLUSTER BY draw_no;
```

---

# 5.3 `prediction_runs`

## 用途

予想生成の実行結果を保存します。

主に以下の用途で使用します。

- 生成された予想番号の履歴保存
- 将来の予想ロジック比較
- どの条件でどの予想が出たかの検証
- 運用監査

## カラム定義（推奨）

| カラム名                | 型        | 必須 | 説明                       |
| ----------------------- | --------- | ---: | -------------------------- |
| `lottery_type`          | STRING    |    ○ | `LOTO6` / `LOTO7`          |
| `draw_no`               | INT64     |      | 対象回号                   |
| `stats_target_draws`    | INT64     |    ○ | 統計対象に使った直近履歴数 |
| `score_snapshot`        | JSON      |    ○ | 数字ごとのスコア           |
| `generated_predictions` | JSON      |    ○ | 生成した5口分の予想番号    |
| `created_at`            | TIMESTAMP |    ○ | 実行時刻                   |

## 推奨 DDL

```sql
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.loto_predict.prediction_runs` (
  lottery_type STRING NOT NULL,
  draw_no INT64,
  stats_target_draws INT64 NOT NULL,
  score_snapshot JSON NOT NULL,
  generated_predictions JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY lottery_type;
```

## JSON の保存例

### `score_snapshot`

```json
{
  "1": 1.95,
  "2": 2.33,
  "3": 0.95,
  "4": 3.12
}
```

### `generated_predictions`

```json
[
  [2, 5, 9, 14, 28, 41],
  [1, 7, 12, 19, 25, 33],
  [3, 8, 16, 21, 34, 40],
  [4, 6, 11, 18, 29, 35],
  [10, 13, 17, 23, 31, 42]
]
```

## 補足

BigQuery では複雑なネスト構造にすることも可能ですが、
このシステムでは実装のシンプルさを優先し、`JSON` 型で保存する方針を推奨します。

---

# 5.4 `execution_logs`（任意）

## 用途

処理結果や障害情報のサマリを保存する補助テーブルです。
Cloud Logging だけでも運用可能ですが、BigQuery にも残しておくと集計や振り返りがしやすくなります。

## カラム定義

| カラム名        | 型        | 必須 | 説明                 |
| --------------- | --------- | ---: | -------------------- |
| `execution_id`  | STRING    |    ○ | 実行単位の ID        |
| `function_name` | STRING    |    ○ | 実行関数名           |
| `lottery_type`  | STRING    |      | `LOTO6` / `LOTO7`    |
| `status`        | STRING    |    ○ | `SUCCESS` / `FAILED` |
| `error_code`    | STRING    |      | エラー分類           |
| `message`       | STRING    |      | 補足メッセージ       |
| `details`       | JSON      |      | 詳細情報             |
| `created_at`    | TIMESTAMP |    ○ | 記録時刻             |

## 推奨 DDL

```sql
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.loto_predict.execution_logs` (
  execution_id STRING NOT NULL,
  function_name STRING NOT NULL,
  lottery_type STRING,
  status STRING NOT NULL,
  error_code STRING,
  message STRING,
  details JSON,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY function_name, status;
```

---

# 6. 推奨クエリ例

---

# 6.1 ロト6の直近100回取得

```sql
SELECT
  draw_no,
  draw_date,
  main_numbers,
  bonus_numbers
FROM `YOUR_PROJECT_ID.loto_predict.loto6_draw_results`
ORDER BY draw_date DESC, draw_no DESC
LIMIT 100;
```

---

# 6.2 ロト7の直近100回取得

```sql
SELECT
  draw_no,
  draw_date,
  main_numbers,
  bonus_numbers
FROM `YOUR_PROJECT_ID.loto_predict.loto7_draw_results`
ORDER BY draw_date DESC, draw_no DESC
LIMIT 100;
```

---

# 6.3 ロト6の数字出現回数集計例

```sql
SELECT
  number,
  COUNT(*) AS appearance_count
FROM `YOUR_PROJECT_ID.loto_predict.loto6_draw_results`,
UNNEST(main_numbers) AS number
GROUP BY number
ORDER BY number;
```

---

# 6.4 ロト7の数字出現回数集計例

```sql
SELECT
  number,
  COUNT(*) AS appearance_count
FROM `YOUR_PROJECT_ID.loto_predict.loto7_draw_results`,
UNNEST(main_numbers) AS number
GROUP BY number
ORDER BY number;
```

---

# 6.5 直近の予想実行履歴取得

```sql
SELECT
  lottery_type,
  draw_no,
  stats_target_draws,
  generated_predictions,
  created_at
FROM `YOUR_PROJECT_ID.loto_predict.prediction_runs`
ORDER BY created_at DESC
LIMIT 20;
```

---

# 7. データ品質方針

BigQuery テーブル上では完全な制約を表現しにくいため、
**アプリケーション側で必ず品質検証** を行います。

## 7.1 検証対象

- `draw_no > 0`
- `draw_date` の形式妥当性
- 本数字件数の妥当性
- ボーナス件数の妥当性
- 数字範囲の妥当性
- 配列内重複禁止
- 本数字とボーナス数字の重複禁止

## 7.2 品質異常時の扱い

- 不正データは保存しない
- ログへ記録する
- ポリシーに応じて「スキップ継続」または「全体停止」

---

# 8. 運用上の推奨

## 8.1 パーティション

- 当選履歴テーブル: `draw_date`
- 実行履歴テーブル: `DATE(created_at)`

これによりクエリスキャン量を抑えやすくなります。

## 8.2 クラスタリング

- 当選履歴テーブル: `draw_no`
- 実行履歴テーブル: `lottery_type`

## 8.3 保持期間

- 当選履歴: 基本永続保持
- `prediction_runs`: 長期保持可
- `execution_logs`: 必要に応じて 90日〜1年程度のライフサイクルを検討
