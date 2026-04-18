from __future__ import annotations

import logging
from io import StringIO

from google.cloud import bigquery

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.infrastructure.serializer.loto_csv import parse_csv_to_rows
from src.utils.logger import get_logger

logger = get_logger()


def import_loto_csv_to_bq(bucket: str, name: str) -> dict[str, object]:
    settings = get_settings()
    storage_client = create_storage_client(settings)
    csv_text = storage_client.download_text(bucket, name)
    rows = parse_csv_to_rows(StringIO(csv_text))
    if not rows:
        raise ValueError("CSV is empty")

    lottery_type = str(rows[0]["lottery_type"]).lower()
    bq_client = None if settings.is_local else bigquery.Client(project=settings.gcp.project_id or None)
    repository = create_loto_repository(bq_client=bq_client)
    result = repository.import_rows(lottery_type=lottery_type, rows=rows)
    logger.info("Imported %s to %s", f"gs://{bucket}/{name}", result.get("table_id") or lottery_type)
    return result
