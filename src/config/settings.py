import os

class Settings:
    PROJECT_ID = os.getenv('GCP_PROJECT_ID')
    REGION = os.getenv('GCP_REGION', 'asia-northeast1')
    DATASET = os.getenv('BQ_DATASET', 'loto_predict')
    RAW_BUCKET = os.getenv('RAW_BUCKET')
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_TO_USER_ID = os.getenv('LINE_TO_USER_ID')
    HISTORY_LIMIT_LOTO6 = int(os.getenv('HISTORY_LIMIT_LOTO6', 100))
    HISTORY_LIMIT_LOTO7 = int(os.getenv('HISTORY_LIMIT_LOTO7', 100))
    TIMEZONE = os.getenv('APP_TIMEZONE', 'Asia/Tokyo')

settings = Settings()
