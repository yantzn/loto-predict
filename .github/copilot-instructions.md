# 🧠 Copilot Instructions - Loto Prediction System

## 🎯 Overview（概要）

This project is a serverless system that:

- Fetches historical Loto6 / Loto7 results
- Stores data in BigQuery
- Generates predictions based on statistics
- Sends predictions via LINE Messaging API

本プロジェクトはロト6・ロト7の過去データをもとに予想番号を生成し、LINE通知するサーバーレスシステムです。

⚠️ This system does NOT guarantee winnings.

---

## 🏗 Architecture

### Tech Stack

- Python 3.11+
- Google Cloud Platform
- BigQuery / Cloud Functions / Scheduler / Storage / Secret Manager
- LINE Messaging API
- Terraform / GitHub Actions

---

## 📁 Project Structure（構成）

```
.
├── functions/
├── src/
│   ├── config/
│   ├── domain/
│   ├── infrastructure/
│   └── usecases/
├── infra/
├── bootstrap/
├── tests/
```

---

## 🧩 Architecture Rules（重要ルール）

Follow these strictly:

- Use layered architecture
- Domain must be pure (no external calls)
- Infrastructure handles external services only
- Usecases orchestrate logic

※責務分離を必ず守ること

---

## 🚫 Forbidden

- Do NOT access BigQuery directly in usecases
- Do NOT mix domain and infrastructure
- Do NOT use os.environ directly

※アンチパターンは禁止

---

## ✅ Required Patterns

### Dataclass

```python
from dataclasses import dataclass

@dataclass
class LotoResult:
    draw_no: int
    numbers: list[int]
```

---

### Pure Function

```python
def calculate_frequency(results):
    ...
```

---

## 🔄 Flow

1. Scheduler triggers
2. Fetch data
3. Store in GCS
4. Import to BigQuery
5. Generate prediction
6. Notify LINE

---

## 📊 Prediction Logic

- Use last N results
- Frequency-based scoring
- Weighted random selection

---

## 📩 Notification

LINE Push API

---

## ⚙️ Env

```
GCP_PROJECT_ID=
BQ_DATASET=
LINE_CHANNEL_ACCESS_TOKEN_SECRET_ID=
```

---

## 🧪 Testing

- domain: unit test
- usecases: integration

---

## 🧠 Copilot Rules（最重要）

- Always use type hints
- Prefer readability
- Keep functions small
- Follow architecture strictly

---

## 💡 Final Rule

Structure > Cleverness
