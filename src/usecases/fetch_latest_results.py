import logging
from src.domain.models import LotoResult
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv
from src.config.settings import get_settings
import os

def fetch_and_save_latest_results(lottery_type: str) -> dict:
    logger = logging.getLogger(__name__)
    settings = get_settings()
    client = RakutenLotoClient()
    result = client.fetch_latest_result(lottery_type)
    result.validate()
    # 保存先パス決定
    filename = f"{lottery_type}_{result.draw_no}.csv"
    if settings.is_local:
        save_dir = os.path.join(settings.local.storage_path, "imported")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
    else:
        save_path = f"gs://{settings.bq_dataset}/imported/{filename}"
    # CSV保存
    with open(save_path, "w", encoding="utf-8", newline="") as f:
        serialize_results_to_csv([result], f)
    logger.info(f"保存: {save_path}")
    return {
        "lottery_type": lottery_type,
        "draw_no": result.draw_no,
        "draw_date": result.draw_date,
        "gcs_uri": save_path,
        "gcs_object": filename,
    }
