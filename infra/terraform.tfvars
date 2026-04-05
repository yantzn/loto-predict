project_id   = "your-gcp-project-id"
region       = "asia-northeast1"
app_timezone = "Asia/Tokyo"

dataset_id = "loto_predict"

runtime                     = "python312"
function_timeout_seconds    = 120
function_available_memory   = "512M"
function_min_instance_count = 0
function_max_instance_count = 1
log_level                   = "INFO"

# null のままなら "${project_id}-loto-raw" が使われる
raw_bucket_name = null

# bootstrap で作成した source bucket
source_bucket_name = "loto-predict-491915-source-6df816"

# deploy-function-source.yml のアップロード先と一致させる
fetch_function_source_object  = "functions/fetch_loto_results/function-source.zip"
import_function_source_object = "functions/import_loto_results/function-source.zip"
notify_function_source_object = "functions/generate_prediction_and_notify/function-source.zip"

# bootstrap で作成した Service Account
functions_runtime_service_account_email = "loto-fn-runtime-6df816@loto-predict-491915.iam.gserviceaccount.com"
scheduler_invoker_service_account_email = "loto-scheduler-invoker-6df816@loto-predict-491915.iam.gserviceaccount.com"

history_limit_loto6 = 100
history_limit_loto7 = 100

line_channel_access_token_secret_id = "line_channel_access_token"
line_user_id_secret_id              = "line_user_id"

scheduler_time_zone = "Asia/Tokyo"
fetch_loto6_cron    = "5 19 * * 1,4"
fetch_loto7_cron    = "5 19 * * 5"
