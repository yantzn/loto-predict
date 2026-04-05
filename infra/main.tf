locals {
  common_labels = {
    system     = "loto-predict-line"
    managed_by = "terraform"
    module     = "infra"
  }

  resolved_raw_bucket_name = coalesce(
    var.raw_bucket_name,
    "${var.project_id}-loto-raw"
  )

  table_ids = {
    loto6_history          = "loto6_history"
    loto7_history          = "loto7_history"
    loto6_validation_stage = "loto6_validation_stage"
    loto7_validation_stage = "loto7_validation_stage"
    prediction_runs        = "prediction_runs"
    execution_logs         = "execution_logs"
  }
}
