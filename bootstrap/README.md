# bootstrap Terraform Runbook

`bootstrap` は `infra` を安全に運用するための土台を作るモジュールです。

主目的は以下です。

- Terraform state 管理用 GCS bucket の作成
- GitHub Actions の鍵レス認証（OIDC / Workload Identity Federation）
- 本体 `infra` が利用する Service Account の事前作成

この構成は、deep-book-ocr の bootstrap 運用思想に合わせています。

---

# 1. 作成されるリソース

## 共通基盤

- Terraform backend 用 GCS bucket（versioning 有効）
- GitHub Actions デプロイ用 Service Account
- Cloud Functions Runtime 用 Service Account
- Workflow runner 用 Service Account
- Cloud Scheduler invoker 用 Service Account

## 認証基盤

- Workload Identity Pool
- Workload Identity Provider
- `roles/iam.workloadIdentityUser` バインディング

## オプション

- Firestore Native database（`enable_firestore=true` 時のみ）

---

# 2. 前提条件

- Terraform `>= 1.5.0`
- GCP プロジェクト作成済み
- 課金有効化済み
- bootstrap を実行できるだけの IAM 権限を持っていること
- `terraform.tfvars` に最低限以下を設定すること
  - `project_id`
  - `github_repository`
  - `github_repository_owner`

---

# 3. GCPログイン

```bash
gcloud auth application-default login
```

# 4. 初回セットアップ

```bash
cd bootstrap
cp terraform.tfvars.example terraform.tfvars

terraform init
terraform validate
terraform plan -lock-timeout=5m -var-file=terraform.tfvars -out=tfplan
terraform apply -lock-timeout=5m tfplan
```
