from __future__ import annotations

import logging
from io import StringIO
from uuid import uuid4

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv


def fetch_and_save_latest_results(lottery_type: str) -> dict[str, object]:
    logger = logging.getLogger(__name__)
    settings = get_settings()
    client = RakutenLotoClient()
    result = client.fetch_latest_result(lottery_type)

    buffer = StringIO()
    serialize_results_to_csv([result], buffer)
    csv_text = buffer.getvalue()

    storage_client = create_storage_client(settings)
    bucket_name = settings.gcp.raw_bucket_name or "local-raw"
    object_name = f"{lottery_type}/draw_no={result.draw_no}/{uuid4().hex}.csv"
    gcs_uri = storage_client.upload_bytes(
        bucket_name=bucket_name,
        blob_name=object_name,
        payload=csv_text.encode("utf-8"),
        content_type="text/csv; charset=utf-8",
    )

    logger.info("保存: %s", gcs_uri)
    return {
        "lottery_type": lottery_type,
        "draw_no": result.draw_no,
        "draw_date": result.draw_date,
        "gcs_uri": gcs_uri,
        "gcs_bucket": bucket_name,
        "gcs_object": object_name,
    }
