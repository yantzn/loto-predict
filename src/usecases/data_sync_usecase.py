from src.infrastructure.bigquery_client import bq_client
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger()

LOTO6_SCHEMA = [
    {'name': 'draw_number', 'type': 'INTEGER'},
    {'name': 'draw_date', 'type': 'DATE'},
    {'name': 'n1', 'type': 'INTEGER'},
    {'name': 'n2', 'type': 'INTEGER'},
    {'name': 'n3', 'type': 'INTEGER'},
    {'name': 'n4', 'type': 'INTEGER'},
    {'name': 'n5', 'type': 'INTEGER'},
    {'name': 'n6', 'type': 'INTEGER'},
    {'name': 'bonus', 'type': 'INTEGER'},
]
LOTO7_SCHEMA = [
    {'name': 'draw_number', 'type': 'INTEGER'},
    {'name': 'draw_date', 'type': 'DATE'},
    {'name': 'n1', 'type': 'INTEGER'},
    {'name': 'n2', 'type': 'INTEGER'},
    {'name': 'n3', 'type': 'INTEGER'},
    {'name': 'n4', 'type': 'INTEGER'},
    {'name': 'n5', 'type': 'INTEGER'},
    {'name': 'n6', 'type': 'INTEGER'},
    {'name': 'n7', 'type': 'INTEGER'},
    {'name': 'bonus1', 'type': 'INTEGER'},
    {'name': 'bonus2', 'type': 'INTEGER'},
]

def import_loto_csv_to_bq(bucket, name):
    # GCS URI
    gcs_uri = f'gs://{bucket}/{name}'
    if 'loto6' in name:
        schema = LOTO6_SCHEMA
        staging = 'loto6_history_staging'
        main = 'loto6_history'
        key = ['draw_number']
    elif 'loto7' in name:
        schema = LOTO7_SCHEMA
        staging = 'loto7_history_staging'
        main = 'loto7_history'
        key = ['draw_number']
    else:
        logger.error('Unknown file type')
        return
    # バリデーション（省略: 必要に応じて追加）
    bq_client.load_csv_to_staging(staging, gcs_uri, schema)
    bq_client.merge_staging_to_main(staging, main, key)
    logger.info(f'Imported {gcs_uri} to {main}')
