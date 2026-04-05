locals {
  common_labels = {
    system     = "loto-predict"
    managed_by = "terraform"
    module     = "infra"
  }

  table_ids = {
    loto6_history          = "loto6_history"
    loto7_history          = "loto7_history"
    prediction_runs        = "prediction_runs"
    execution_logs         = "execution_logs"
    loto6_validation_stage = "loto6_validation_stage"
    loto7_validation_stage = "loto7_validation_stage"
  }
}
