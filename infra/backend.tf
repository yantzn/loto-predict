terraform {
  backend "gcs" {
    prefix = "loto-predict/infra"
  }
}
