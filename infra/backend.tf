terraform {
  backend "gcs" {
    # validate時の必須チェック用。実際の値は init -backend-config で上書きする。
    bucket = "placeholder-tfstate-bucket"
    prefix = "loto-predict/infra"
  }
}
