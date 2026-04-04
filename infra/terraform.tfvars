app_timezone = "Asia/Tokyo"

dataset_id = "loto_predict"

runtime                   = "python312"
function_timeout_seconds  = 120
function_available_memory = "512M"
log_level                 = "INFO"

# null のままなら "${project_id}-loto-raw" が使われる
raw_bucket_name = null

# GitHub Actions から渡すBQ_DATASET値（なければデフォルト）
bq_dataset = "loto_predict"
