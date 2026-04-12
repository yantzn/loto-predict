from __future__ import annotations

import os


class Settings:
    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "local")
        self.local_storage_path: str = os.getenv("LOCAL_STORAGE_PATH", "./local_storage")

        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
        self.region: str = os.getenv("GCP_REGION", "asia-northeast1")

        self.bigquery_dataset: str = os.getenv("BIGQUERY_DATASET", os.getenv("BQ_DATASET", "loto_predict"))
        self.gcs_bucket_raw: str = os.getenv("GCS_BUCKET_RAW", os.getenv("RAW_BUCKET", ""))

        self.line_channel_access_token: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        self.line_to_user_id: str = os.getenv("LINE_TO_USER_ID", "")

        self.history_limit_loto6: int = int(os.getenv("HISTORY_LIMIT_LOTO6", "100"))
        self.history_limit_loto7: int = int(os.getenv("HISTORY_LIMIT_LOTO7", "100"))

        self.timezone: str = os.getenv("APP_TIMEZONE", "Asia/Tokyo")


settings = Settings()
