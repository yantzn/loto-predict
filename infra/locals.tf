locals {
  common_labels = {
    system     = "loto-predict"
    managed_by = "terraform"
    module     = "infra"
  }

  function_source_objects = {
    fetch  = "functions/fetch_loto_results/function-source.zip"
    import = "functions/import_loto_results_to_bq/function-source.zip"
    notify = "functions/generate_prediction_and_notify/function-source.zip"
  }

  backfill_job_name = "backfill-loto-history"

  table_ids = {
    loto6_history   = "loto6_history"
    loto7_history   = "loto7_history"
    prediction_runs = "prediction_runs"
    execution_logs  = "execution_logs"
  }
}
